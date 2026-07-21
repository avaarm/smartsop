"""SQLite database models for account-scoped GMP document storage and training data."""

import os
import sqlite3
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Default DB path (can be overridden via DATABASE_URL env var)
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "smartsop.db")


def _normalize_db_url(url: str) -> str:
    """Accept the legacy `postgres://` scheme that some platforms still hand out."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _apply_sqlite_pragmas(dbapi_conn, _record):
    """Tune SQLite for concurrent access. No-op for non-SQLite backends.

    WAL lets readers run while a writer is active, and a busy timeout makes
    concurrent writers wait for the lock instead of failing immediately —
    the two biggest sources of "database is locked" errors under load.
    """
    if isinstance(dbapi_conn, sqlite3.Connection):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def init_db(app):
    """Initialize the database with the Flask app.

    Works with the zero-config SQLite default and with a pooled Postgres
    (or other) backend via DATABASE_URL, so the app can scale from a laptop
    to multiple stateless instances behind a load balancer.
    """
    db_url = _normalize_db_url(
        os.environ.get("DATABASE_URL", f"sqlite:///{os.path.abspath(DEFAULT_DB_PATH)}")
    )
    is_sqlite = db_url.startswith("sqlite")

    engine_options = {
        # Recycle/validate pooled connections so a stale or dropped server-side
        # connection (idle timeout, failover) doesn't surface as a 500.
        "pool_pre_ping": True,
        "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE", 1800)),
    }
    if is_sqlite:
        # SQLite connections are bound to the creating thread by default; relax
        # that so the pool can hand them to gunicorn worker threads.
        engine_options["connect_args"] = {"check_same_thread": False}
    else:
        # Per-worker connection pool. Keep pool_size in line with the number of
        # threads each gunicorn worker runs (see gunicorn.conf.py).
        engine_options["pool_size"] = int(os.environ.get("DB_POOL_SIZE", 10))
        engine_options["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", 20))
        engine_options["pool_timeout"] = int(os.environ.get("DB_POOL_TIMEOUT", 30))

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options

    db.init_app(app)
    with app.app_context():
        if is_sqlite:
            event.listen(db.engine, "connect", _apply_sqlite_pragmas)
        # Zero-config default: create tables directly. Set AUTO_CREATE_TABLES=false
        # in production to let Alembic migrations (flask db upgrade) own the schema.
        if os.environ.get("AUTO_CREATE_TABLES", "true").lower() in ("1", "true", "yes"):
            db.create_all()


class User(db.Model):
    """A person who logs in. Users access accounts (tenants) through memberships."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), default="")
    password_hash = db.Column(db.String(255), nullable=False)

    # Platform administrator: can see and manage every account.
    is_superadmin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    memberships = db.relationship(
        "Membership", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_memberships: bool = False):
        d = {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "is_superadmin": self.is_superadmin,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_memberships:
            d["memberships"] = [m.to_dict() for m in self.memberships]
        return d


class Membership(db.Model):
    """Links a user to an account with a role. This is what enforces tenant isolation."""

    __tablename__ = "memberships"
    __table_args__ = (
        db.UniqueConstraint("user_id", "account_id", name="uq_user_account"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    role = db.Column(db.String(50), default="member", nullable=False)  # owner, admin, member
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship("Account")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "role": self.role,
            "account_name": self.account.name if self.account else None,
            "account_slug": self.account.slug if self.account else None,
        }


class Account(db.Model):
    """An organization / facility account. All documents and training data are scoped to an account."""

    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    facility_name = db.Column(db.String(300), default="")
    department = db.Column(db.String(200), default="")

    # Org-specific defaults injected into every LLM prompt
    default_product = db.Column(db.String(200), default="")
    default_process = db.Column(db.String(200), default="")
    terminology_json = db.Column(db.Text, default="{}")  # custom terms & abbreviations
    style_notes = db.Column(db.Text, default="")  # free-text style instructions for AI
    reference_sops_json = db.Column(db.Text, default="[]")  # org's standard SOP list

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = db.relationship("Document", backref="account", lazy="dynamic")
    training_examples = db.relationship("TrainingExample", backref="account", lazy="dynamic")

    def to_dict(self, counts=None):
        """Serialize the account.

        Pass `counts={"documents": int, "training": int}` (e.g. computed in
        bulk for a list) to avoid a per-account count query (N+1). When omitted,
        the two counts are queried individually — fine for a single account.
        """
        if counts is None:
            document_count = self.documents.count()
            training_example_count = self.training_examples.count()
        else:
            document_count = counts.get("documents", 0)
            training_example_count = counts.get("training", 0)
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "facility_name": self.facility_name,
            "department": self.department,
            "default_product": self.default_product,
            "default_process": self.default_process,
            "terminology": self.terminology_json,
            "style_notes": self.style_notes,
            "reference_sops": self.reference_sops_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "document_count": document_count,
            "training_example_count": training_example_count,
        }


class Document(db.Model):
    """A generated GMP document, stored for history and training data collection."""

    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    doc_type = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    product_name = db.Column(db.String(200), default="")
    process_type = db.Column(db.String(200), default="")
    description = db.Column(db.Text, default="")
    doc_number = db.Column(db.String(100), default="")
    revision = db.Column(db.String(20), default="01")

    # Full section data as JSON (the input that produced the DOCX)
    sections_json = db.Column(db.Text, default="{}")
    filename = db.Column(db.String(500), default="")
    file_path = db.Column(db.String(1000), default="")

    status = db.Column(db.String(50), default="generated")  # generated, reviewed, approved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Approval audit trail. Names are denormalized (captured at the time of the
    # action) so the record is preserved even if a user is later renamed/removed.
    reviewed_by = db.Column(db.String(255), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.String(255), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

    training_examples = db.relationship("TrainingExample", backref="document", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "doc_type": self.doc_type,
            "title": self.title,
            "product_name": self.product_name,
            "process_type": self.process_type,
            "description": self.description,
            "doc_number": self.doc_number,
            "revision": self.revision,
            "filename": self.filename,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }


class TrainingExample(db.Model):
    """A single prompt -> completion pair captured for fine-tuning.

    Every time the LLM generates a section and the user keeps or edits it,
    we store the (prompt, completion) pair. If the user edits the AI output,
    the edited version becomes the completion (higher quality signal).
    """

    __tablename__ = "training_examples"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)

    # What we asked the LLM
    section_type = db.Column(db.String(100), nullable=False)
    system_prompt = db.Column(db.Text, default="")
    user_prompt = db.Column(db.Text, nullable=False)

    # What we got back (or what the user corrected it to)
    completion = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(50), default="ai")  # ai, user_edited, manual
    quality_rating = db.Column(db.Integer, nullable=True)  # 1-5 optional rating

    # Context that produced this example
    product_name = db.Column(db.String(200), default="")
    process_type = db.Column(db.String(200), default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "document_id": self.document_id,
            "section_type": self.section_type,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "completion": self.completion,
            "source": self.source,
            "quality_rating": self.quality_rating,
            "product_name": self.product_name,
            "process_type": self.process_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_training_format(self, include_system=True):
        """Export as a fine-tuning training row (Llama 3 chat format)."""
        messages = []
        if include_system and self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": self.user_prompt})
        messages.append({"role": "assistant", "content": self.completion})
        return {"messages": messages}


class Protocol(db.Model):
    """A protocols.io-style step-by-step method that can be edited, run, and shared.

    Unlike a one-shot generated Document, a Protocol is a living, versioned,
    ordered list of steps that a user executes ("runs") in the lab.
    """

    __tablename__ = "protocols"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)

    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, default="")   # abstract / overview

    # protocol | sop | gmp_sop — a GMP SOP is a controlled document with an
    # enforced review/approval lifecycle and e-signatures.
    protocol_type = db.Column(db.String(30), default="protocol")

    # Controlled-document lifecycle: draft -> in_review -> approved -> effective
    # -> retired. (Legacy "published" is treated as effective.)
    status = db.Column(db.String(50), default="draft")
    version = db.Column(db.Integer, default=1, nullable=False)
    created_by = db.Column(db.String(255), default="")   # denormalized author name

    # SOP control metadata
    sop_number = db.Column(db.String(100), default="")
    department = db.Column(db.String(200), default="")
    effective_date = db.Column(db.String(30), default="")   # ISO date, set when made effective
    review_date = db.Column(db.String(30), default="")      # next periodic review

    # Versioning chain: a new version points at the id it supersedes. Kept as a
    # plain integer (soft reference) to avoid a self-referential FK, which
    # SQLite's batch ALTER can't add cleanly.
    supersedes_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    steps = db.relationship(
        "ProtocolStep", backref="protocol", lazy="dynamic",
        cascade="all, delete-orphan", order_by="ProtocolStep.order_index",
    )
    signoffs = db.relationship(
        "ProtocolSignoff", backref="protocol", lazy="dynamic",
        cascade="all, delete-orphan", order_by="ProtocolSignoff.signed_at",
    )

    def to_dict(self, include_steps=False):
        d = {
            "id": self.id,
            "account_id": self.account_id,
            "title": self.title,
            "description": self.description,
            "protocol_type": self.protocol_type,
            "status": self.status,
            "version": self.version,
            "created_by": self.created_by,
            "sop_number": self.sop_number,
            "department": self.department,
            "effective_date": self.effective_date,
            "review_date": self.review_date,
            "supersedes_id": self.supersedes_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "step_count": self.steps.count(),
            "signoffs": [s.to_dict() for s in self.signoffs],
        }
        if include_steps:
            d["steps"] = [s.to_dict() for s in self.steps]
        return d


class ProtocolSignoff(db.Model):
    """An electronic signature on a protocol version (21 CFR Part 11 style).

    Records who signed, when, in what role, the *meaning* of the signature, and
    the decision — an immutable audit trail of the review/approval lifecycle.
    """

    __tablename__ = "protocol_signoffs"

    id = db.Column(db.Integer, primary_key=True)
    protocol_id = db.Column(db.Integer, db.ForeignKey("protocols.id"), nullable=False)

    role = db.Column(db.String(30), nullable=False)      # author, reviewer, approver
    decision = db.Column(db.String(30), nullable=False)  # approved, rejected
    meaning = db.Column(db.String(300), default="")      # meaning-of-signature statement
    comment = db.Column(db.Text, default="")

    signed_by = db.Column(db.String(255), default="")    # denormalized name at signing
    signed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    signed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "protocol_id": self.protocol_id,
            "role": self.role,
            "decision": self.decision,
            "meaning": self.meaning,
            "comment": self.comment,
            "signed_by": self.signed_by,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
        }


class ProtocolRun(db.Model):
    """An execution of a protocol — protocols.io's "run record".

    A run snapshots the protocol's steps at start time so later edits to the
    protocol don't rewrite history, and records who did what and when.
    """

    __tablename__ = "protocol_runs"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    protocol_id = db.Column(db.Integer, db.ForeignKey("protocols.id"), nullable=False)

    protocol_title = db.Column(db.String(500), default="")   # snapshot at start
    protocol_version = db.Column(db.Integer, default=1)
    experiment_id = db.Column(db.String(200), default="")
    status = db.Column(db.String(50), default="running")      # running, completed

    started_by = db.Column(db.String(255), default="")
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    run_steps = db.relationship(
        "ProtocolRunStep", backref="run", lazy="dynamic",
        cascade="all, delete-orphan", order_by="ProtocolRunStep.order_index",
    )

    def progress(self):
        total = self.run_steps.count()
        done = self.run_steps.filter(ProtocolRunStep.status != "pending").count()
        return done, total

    def to_dict(self, include_steps=False):
        done, total = self.progress()
        d = {
            "id": self.id,
            "account_id": self.account_id,
            "protocol_id": self.protocol_id,
            "protocol_title": self.protocol_title,
            "protocol_version": self.protocol_version,
            "experiment_id": self.experiment_id,
            "status": self.status,
            "started_by": self.started_by,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "completed_steps": done,
            "total_steps": total,
        }
        if include_steps:
            d["steps"] = [s.to_dict() for s in self.run_steps]
        return d


class ProtocolRunStep(db.Model):
    """One step within a run: the snapshotted instruction plus its outcome."""

    __tablename__ = "protocol_run_steps"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("protocol_runs.id"), nullable=False)
    step_id = db.Column(db.Integer, nullable=True)   # original step (may later be deleted)

    order_index = db.Column(db.Integer, default=0, nullable=False)
    title = db.Column(db.String(500), default="")
    description = db.Column(db.Text, default="")
    duration_seconds = db.Column(db.Integer, nullable=True)
    warning = db.Column(db.Text, default="")
    reagents_json = db.Column(db.Text, default="[]")
    components_json = db.Column(db.Text, default="[]")
    branch_json = db.Column(db.Text, default="")

    # Outcome — protocols.io offers Done / Fail / Skip, not a binary checkbox.
    status = db.Column(db.String(50), default="pending")   # pending, done, failed, skipped
    note = db.Column(db.Text, default="")                  # recorded observation
    completed_by = db.Column(db.String(255), default="")
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        import json as _json
        try:
            reagents = _json.loads(self.reagents_json or "[]")
        except ValueError:
            reagents = []
        try:
            components = _json.loads(self.components_json or "[]")
        except ValueError:
            components = []
        try:
            branch = _json.loads(self.branch_json) if self.branch_json else None
        except ValueError:
            branch = None
        return {
            "id": self.id,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "order_index": self.order_index,
            "title": self.title,
            "description": self.description,
            "duration_seconds": self.duration_seconds,
            "warning": self.warning,
            "reagents": reagents,
            "components": components,
            "branch": branch,
            "status": self.status,
            "note": self.note,
            "completed_by": self.completed_by,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ProtocolStep(db.Model):
    """One ordered step of a protocol, with optional structured components."""

    __tablename__ = "protocol_steps"

    id = db.Column(db.Integer, primary_key=True)
    protocol_id = db.Column(db.Integer, db.ForeignKey("protocols.id"), nullable=False)

    order_index = db.Column(db.Integer, default=0, nullable=False)
    section = db.Column(db.String(200), default="")   # optional grouping heading
    title = db.Column(db.String(500), default="")
    description = db.Column(db.Text, default="")       # the instruction text

    # protocols.io-style components
    duration_seconds = db.Column(db.Integer, nullable=True)   # timer for this step
    warning = db.Column(db.Text, default="")                  # safety / caution note
    reagents_json = db.Column(db.Text, default="[]")          # [{name, amount, vendor}]
    # Typed LOTO/safety blocks: [{type, value}] e.g. {type:"ppe", value:"Arc suit"}
    components_json = db.Column(db.Text, default="[]")
    # Optional decision/branch: {"question","options":[{label,action,target}]}
    branch_json = db.Column(db.Text, default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        import json as _json
        try:
            reagents = _json.loads(self.reagents_json or "[]")
        except ValueError:
            reagents = []
        try:
            components = _json.loads(self.components_json or "[]")
        except ValueError:
            components = []
        try:
            branch = _json.loads(self.branch_json) if self.branch_json else None
        except ValueError:
            branch = None
        return {
            "id": self.id,
            "protocol_id": self.protocol_id,
            "order_index": self.order_index,
            "section": self.section,
            "title": self.title,
            "description": self.description,
            "duration_seconds": self.duration_seconds,
            "warning": self.warning,
            "reagents": reagents,
            "components": components,
            "branch": branch,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
