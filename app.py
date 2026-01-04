from flask import Flask, jsonify
from mongoengine import (
    connect, Document, EmbeddedDocument,
    StringField, BooleanField, IntField,
    ListField, ReferenceField, EmbeddedDocumentField
)
from flask_cors import CORS
from bson import ObjectId


# -------------------------------------------------
# DATABASE CONNECTION (MongoDB Atlas)
# -------------------------------------------------

connect(
    db="upsc",
    host="mongodb+srv://user:user@cluster0.rgocxdb.mongodb.net/upsc"
)

app = Flask(__name__)

# -------------------------------------------------
# MODELS
# -------------------------------------------------

class SubTopic(Document):
    name = StringField(required=True)
    subject = StringField(required=True)

    v1_generated = BooleanField(default=False)
    v2_cleaned = BooleanField(default=False)
    v3_verified = BooleanField(default=False)
    v4_finalized = BooleanField(default=False)

    meta = {
        "collection": "subtopics",
        "indexes": [{"fields": ["name", "subject"], "unique": True}]
    }


class UPSCSyllabus(Document):
    exam = StringField(required=True, default="UPSC Civil Services Examination")
    stage = StringField(required=True)
    paper = StringField(required=True)
    subject = StringField(required=True)

    subtopics = ListField(ReferenceField(SubTopic))

    v1 = BooleanField(default=False)
    v2 = BooleanField(default=False)
    v3 = BooleanField(default=False)
    v4 = BooleanField(default=False)

    meta = {
        "collection": "upsc_syllabus",
        "indexes": ["subject", ("stage", "paper")]
    }


class MicroUnit(Document):
    name = StringField(required=True)
    subject = StringField(required=True)
    subtopic = ReferenceField(SubTopic, required=True)
    order = IntField(default=0)

    v5_generated = BooleanField(default=False)
    v6_verified = BooleanField(default=False)
    v6_finalized = BooleanField(default=False)

    meta = {
        "collection": "micro_units",
        "indexes": ["subject", ("subtopic", "name")],
        "unique_with": ["subtopic"]
    }


class MicroUnitNote(Document):
    micro_unit = ReferenceField(MicroUnit, required=True, unique=True)
    content = StringField(required=True)

    # legacy fields (keep for compatibility)
    word_count = IntField()
    image_required = BooleanField(default=False)
    image_reasons = ListField(StringField())

    v1_generated = BooleanField(default=False)
    v1_verified = BooleanField(default=False)

    meta = {
        "collection": "micro_unit_notes",
        "indexes": ["micro_unit"]
    }



class MCQOptionDoc(EmbeddedDocument):
    option = StringField(required=True)
    text = StringField(required=True)


class IndividualMCQDoc(EmbeddedDocument):
    question_number = IntField(required=True)
    question_text = StringField(required=True)
    options = ListField(EmbeddedDocumentField(MCQOptionDoc), required=True)
    correct_answer = StringField(required=True)
    explanation = StringField(required=True)
    additional_notes = StringField()
    image_required = BooleanField(default=False)
    image_reason = StringField()


class MicroUnitMCQ(Document):
    micro_unit = ReferenceField(MicroUnit, required=True, unique=True)

    mcq_count = IntField(required=True)
    mcqs = ListField(EmbeddedDocumentField(IndividualMCQDoc), required=True)
    remarks = StringField()
    commentary = StringField()
    content = StringField(required=True)

    image_required = BooleanField(default=False)
    image_reasons = ListField(StringField())

    v1_generated = BooleanField(default=False)
    v1_verified = BooleanField(default=False)

    meta = {
        "collection": "micro_unit_mcqs",
        "indexes": ["micro_unit"]
    }

# -------------------------------------------------
# ROUTES (READ-ONLY)
# -------------------------------------------------

@app.route("/subjects")
def list_subjects():
    subjects = UPSCSyllabus.objects(v4=True).distinct("subject")
    return jsonify(subjects)


@app.route("/syllabus/<subject>")
def syllabus_by_subject(subject):
    syllabus = UPSCSyllabus.objects(subject=subject, v4=True)
    return jsonify([
        {
            "stage": s.stage,
            "paper": s.paper,
            "exam": s.exam
        } for s in syllabus
    ])

@app.route("/subtopics/<subject>")
def subtopics_by_subject(subject):
    subtopics = SubTopic.objects(subject=subject)

    micro_units = MicroUnit.objects(subtopic__in=subtopics)

    noted_units = set(
        MicroUnitNote.objects(
            micro_unit__in=micro_units
        ).distinct("micro_unit")
    )

    subtopic_has_notes = {}
    # print(noted_units)

    for mu in micro_units:
        print(mu.id)
        if mu.id in noted_units:
            print(mu.subtopic.id)
            subtopic_has_notes[mu.subtopic.id] = True

    return jsonify([
        {
            "name": s.name,
            "has_notes": subtopic_has_notes.get(s.id, False)
        }
        for s in subtopics
    ])


@app.route("/micro-units/<subject>/<subtopic_name>")
def micro_units_by_subtopic(subject, subtopic_name):
    subtopic = SubTopic.objects.get(
        name=subtopic_name,
        subject=subject,
        v4_finalized=True
    )

    units = MicroUnit.objects(
        subtopic=subtopic,
        v6_finalized=True
    ).order_by("order")

    # fetch all micro_unit ids that already have notes
    notes_map = set(
        MicroUnitNote.objects(
            micro_unit__in=units
        ).distinct("micro_unit")
    )
    print(notes_map)

    return jsonify([
        {
            "id": str(u.id),
            "name": u.name,
            "order": u.order,
            "has_notes": u in notes_map
        }
        for u in units
    ])


@app.route("/notes/<micro_unit_id>")
def notes_by_micro_unit(micro_unit_id):
    micro_unit = MicroUnit.objects.get(id=ObjectId(micro_unit_id))
    print(micro_unit)
    note = MicroUnitNote.objects.get(micro_unit=micro_unit)
    return jsonify({
        "micro_unit_id": micro_unit_id,
        "content": note.content
    })


@app.route("/mcqs/<micro_unit_id>")
def mcqs_by_micro_unit(micro_unit_id):
    mcq = MicroUnitMCQ.objects.get(micro_unit=micro_unit_id)

    return jsonify({
        "mcq_count": mcq.mcq_count,
        "mcqs": [
            {
                "question_number": q.question_number,
                "question_text": q.question_text,
                "options": [
                    {"option": o.option, "text": o.text}
                    for o in q.options
                ],
                "correct_answer": q.correct_answer,
                "explanation": q.explanation,
                "additional_notes": q.additional_notes,
                "image_required": q.image_required,
                "image_reason": q.image_reason
            }
            for q in mcq.mcqs
        ]
    })

# -------------------------------------------------
# APP ENTRY
# -------------------------------------------------
CORS(app)

if __name__ == "__main__":
    app.run(debug=True)
