"""SQLite database models for account-scoped GMP document storage and training data."""

import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Default DB path (can be overridden via DATABASE_URL env var)
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "smartsop.db")


def init_db(app):
    """Initialize the database with the Flask app."""
    db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.abspath(DEFAULT_DB_PATH)}")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()


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

    def to_dict(self):
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
            "document_count": self.documents.count(),
            "training_example_count": self.training_examples.count(),
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
