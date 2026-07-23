"""Prebuilt regulatory SOP templates.

A new workspace should not open on an empty list. These are opinionated
starting points aligned to the standards our buyers are audited against, with
the typed LOTO/safety blocks already filled in — so a customer sees a
competent skeleton on day one instead of a blank editor.

They are deliberately *starting points*: every template lands as a draft that
must go through the normal review/approval lifecycle before it is effective.
"""

# Each template: key, name, standard, description, category, and steps.
# Step components use the same {type, value} vocabulary as COMPONENT_TYPES.
TEMPLATES = [
    {
        "key": "loto_1910_147",
        "name": "Lockout/Tagout — Machine Isolation",
        "standard": "OSHA 1910.147",
        "category": "Energy control",
        "description": (
            "The Control of Hazardous Energy. Covers isolation, lockout application, "
            "stored-energy release, verification, and return to service."
        ),
        "protocol_type": "sop",
        "steps": [
            {
                "title": "Notify affected employees",
                "description": (
                    "Inform all affected employees that a lockout/tagout is about to be "
                    "applied and the equipment will be shut down."
                ),
                "components": [{"type": "authorized_person", "value": "Authorized employee performing the LOTO"}],
            },
            {
                "title": "Identify all energy sources",
                "description": (
                    "Review the equipment's energy-control procedure. Identify every energy "
                    "source: electrical, hydraulic, pneumatic, mechanical, thermal, chemical, "
                    "and gravitational."
                ),
                "components": [
                    {"type": "energy_source", "value": "List every source — see the asset record"},
                    {"type": "hazard_class", "value": "Determine from the equipment's arc-flash / hazard label"},
                ],
            },
            {
                "title": "Don required PPE",
                "description": "Put on the PPE required for the hazard class before approaching the equipment.",
                "components": [{"type": "ppe", "value": "Per hazard class — e.g. arc-rated clothing, gloves, face shield"}],
            },
            {
                "title": "Shut down the equipment",
                "description": (
                    "Shut down using the normal stopping procedure. Do not use the disconnect "
                    "as an on/off switch."
                ),
            },
            {
                "title": "Isolate each energy source",
                "description": (
                    "Operate each disconnect, valve, or isolating device to fully isolate the "
                    "equipment from every energy source identified."
                ),
                "components": [{"type": "isolation_device", "value": "Record each device operated"}],
            },
            {
                "title": "Apply locks and tags",
                "description": (
                    "Each authorized employee applies their own personally assigned lock and "
                    "tag to every isolating device. Tags must identify who applied them."
                ),
                "components": [
                    {"type": "lockout_tag", "value": "Record each tag ID applied"},
                    {"type": "verification_photo", "value": True},
                ],
            },
            {
                "title": "Release stored energy",
                "description": (
                    "Relieve, disconnect, restrain, or otherwise render safe all stored or "
                    "residual energy: capacitors, springs, elevated members, rotating flywheels, "
                    "hydraulic and pneumatic pressure."
                ),
                "components": [{"type": "pressure", "value": "Verify bled to 0"}],
            },
            {
                "title": "Verify isolation (try-out)",
                "description": (
                    "Verify the equipment cannot start. Test with a meter where applicable "
                    "(live-dead-live), then attempt a normal start and return controls to off."
                ),
                "duration_seconds": 300,
                "components": [
                    {"type": "expected_result", "value": "Zero energy confirmed at the point of work"},
                    {"type": "second_signature", "value": True},
                ],
                "warning": "Do not begin work until zero-energy state has been positively verified.",
            },
            {
                "title": "Perform the servicing work",
                "description": "Carry out the maintenance or servicing task the lockout was applied for.",
            },
            {
                "title": "Return to service",
                "description": (
                    "Confirm the work area is clear of tools and personnel, reinstall guards, "
                    "remove each lock/tag by the person who applied it, then restore energy and "
                    "notify affected employees."
                ),
                "components": [
                    {"type": "return_to_service", "value": "Guards reinstalled, area clear, all locks removed by owner"},
                    {"type": "second_signature", "value": True},
                ],
            },
        ],
    },
    {
        "key": "confined_space_1910_146",
        "name": "Permit-Required Confined Space Entry",
        "standard": "OSHA 1910.146",
        "category": "Confined space",
        "description": (
            "Entry into a permit-required confined space: atmospheric testing, ventilation, "
            "attendant duties, and rescue provisions."
        ),
        "protocol_type": "sop",
        "steps": [
            {
                "title": "Issue the entry permit",
                "description": (
                    "Complete and post the entry permit. It must identify the space, the purpose, "
                    "the hazards, the entrants, the attendant, and the entry supervisor."
                ),
                "components": [{"type": "authorized_person", "value": "Entry supervisor"}],
            },
            {
                "title": "Isolate the space",
                "description": (
                    "Lock out and blank/blind all lines that could introduce energy or material "
                    "into the space. Complete the LOTO procedure first where applicable."
                ),
                "components": [{"type": "isolation_device", "value": "Blanks, blinds, and LOTO devices"}],
            },
            {
                "title": "Test the atmosphere",
                "description": (
                    "Test in order: oxygen, then flammable gases and vapours, then toxic air "
                    "contaminants. Test before entry and continuously or periodically during entry."
                ),
                "components": [
                    {"type": "expected_result", "value": "O2 19.5–23.5% · LEL <10% · toxics below PEL"},
                    {"type": "verification_photo", "value": True},
                ],
                "warning": "Never enter to test. Test from outside the space.",
            },
            {
                "title": "Ventilate",
                "description": "Provide continuous forced-air ventilation as required and re-test after ventilating.",
                "duration_seconds": 900,
            },
            {
                "title": "Don PPE and retrieval equipment",
                "description": (
                    "Entrants don required PPE, harness, and retrieval line attached to a "
                    "mechanical retrieval device where required."
                ),
                "components": [{"type": "ppe", "value": "Harness, retrieval line, respiratory protection as required"}],
            },
            {
                "title": "Station the attendant",
                "description": (
                    "The attendant remains outside for the duration, maintains an accurate entrant "
                    "count, and never enters the space to attempt rescue."
                ),
                "components": [{"type": "authorized_person", "value": "Attendant (remains outside)"}],
            },
            {
                "title": "Perform entry and work",
                "description": "Entrants perform the work while communication and monitoring are maintained.",
            },
            {
                "title": "Exit and close the permit",
                "description": (
                    "All entrants exit, the attendant confirms the count, equipment is removed, "
                    "and the entry supervisor closes and retains the permit."
                ),
                "components": [{"type": "second_signature", "value": True}],
            },
        ],
    },
    {
        "key": "arc_flash_nfpa_70e",
        "name": "Energized Electrical Work — Arc Flash",
        "standard": "NFPA 70E",
        "category": "Electrical safety",
        "description": (
            "Electrically safe work practices: risk assessment, approach boundaries, arc-rated "
            "PPE selection, and the energized work permit."
        ),
        "protocol_type": "sop",
        "steps": [
            {
                "title": "Justify energized work",
                "description": (
                    "Establish that de-energizing introduces additional hazards or is infeasible. "
                    "If not justified, stop and de-energize using the LOTO procedure."
                ),
                "components": [{"type": "authorized_person", "value": "Qualified person + management approval"}],
                "warning": "De-energizing is the default. Energized work requires written justification.",
            },
            {
                "title": "Complete the arc-flash risk assessment",
                "description": (
                    "Determine the incident energy or arc-flash PPE category, the arc-flash "
                    "boundary, and the limited/restricted approach boundaries."
                ),
                "components": [{"type": "hazard_class", "value": "Incident energy (cal/cm²) or PPE category"}],
            },
            {
                "title": "Issue the energized electrical work permit",
                "description": "Complete the permit with the job scope, the assessment results, and the required approvals.",
                "components": [{"type": "second_signature", "value": True}],
            },
            {
                "title": "Select and inspect arc-rated PPE",
                "description": (
                    "Select PPE meeting or exceeding the assessed incident energy. Inspect rubber "
                    "insulating gloves for damage and confirm they are within test date."
                ),
                "components": [
                    {"type": "ppe", "value": "Arc-rated suit/hood, voltage-rated gloves, face shield"},
                    {"type": "verification_photo", "value": True},
                ],
            },
            {
                "title": "Establish the work area boundary",
                "description": "Barricade the arc-flash boundary and post warning signs. Only qualified persons inside.",
            },
            {
                "title": "Verify absence of voltage where applicable",
                "description": "Use a properly rated tester with the live-dead-live method on a known source.",
                "components": [{"type": "expected_result", "value": "Tester proven before and after"}],
            },
            {
                "title": "Perform the work",
                "description": "Carry out the task using insulated tools and maintaining approach boundaries.",
            },
            {
                "title": "Close out",
                "description": "Remove barricades, restore the area, and close the permit.",
                "components": [{"type": "return_to_service", "value": "Area restored, permit closed"}],
            },
        ],
    },
    {
        "key": "haccp_ccp_monitoring",
        "name": "HACCP — Critical Control Point Monitoring",
        "standard": "HACCP / FSMA",
        "category": "Food safety",
        "description": (
            "Monitoring a critical control point: measurement against critical limits, "
            "corrective action on deviation, and verification recordkeeping."
        ),
        "protocol_type": "gmp_sop",
        "steps": [
            {
                "title": "Identify the CCP and its critical limit",
                "description": (
                    "Confirm which critical control point is being monitored and the critical "
                    "limit from the HACCP plan."
                ),
                "components": [{"type": "expected_result", "value": "Critical limit per the HACCP plan"}],
            },
            {
                "title": "Verify the monitoring instrument",
                "description": "Confirm the thermometer or instrument is calibrated and within its calibration due date.",
                "components": [
                    {"type": "temperature", "value": "Calibration verified against reference"},
                    {"type": "verification_photo", "value": True},
                ],
            },
            {
                "title": "Take the measurement",
                "description": "Measure at the defined location and frequency, and record the actual value observed.",
                "components": [{"type": "temperature", "value": "Record the actual reading"}],
            },
            {
                "title": "Compare against the critical limit",
                "description": (
                    "If the reading is within the critical limit, continue. If it is outside, "
                    "the branch below routes to corrective action."
                ),
                "branch": {
                    "question": "Is the measurement within the critical limit?",
                    "options": [
                        {"label": "Yes — within limit", "action": "goto", "target": 6},
                        {"label": "No — deviation", "action": "continue", "target": None},
                    ],
                },
            },
            {
                "title": "Take corrective action",
                "description": (
                    "Segregate and hold the affected product, correct the process, determine the "
                    "disposition of affected product, and record the deviation."
                ),
                "components": [{"type": "authorized_person", "value": "Qualified individual"}],
                "warning": "Affected product must be held until disposition is determined.",
            },
            {
                "title": "Record and verify",
                "description": (
                    "Sign the monitoring record. A reviewer verifies records within the timeframe "
                    "required by the plan."
                ),
                "components": [{"type": "second_signature", "value": True}],
            },
        ],
    },
]


def template_summaries():
    """The gallery listing — everything except the step bodies."""
    return [
        {
            "key": t["key"],
            "name": t["name"],
            "standard": t["standard"],
            "category": t["category"],
            "description": t["description"],
            "protocol_type": t["protocol_type"],
            "step_count": len(t["steps"]),
        }
        for t in TEMPLATES
    ]


def get_template(key):
    return next((t for t in TEMPLATES if t["key"] == key), None)
