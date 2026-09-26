import pytest


def test_create_get_list_update_delete(mongo, sample_meeting):
    first = mongo.create_meeting(sample_meeting)
    second = mongo.create_meeting(dict(sample_meeting, title="Later meeting", meeting_date="2026-09-25"))

    listed = mongo.list_meetings()
    assert [m["title"] for m in listed] == ["Later meeting", "Q3 budget review"]
    assert "transcript" not in listed[0]

    loaded = mongo.get_meeting(first)
    assert loaded["id"] == first and loaded["minutes"]["summary"].startswith("The team reviewed")

    assert mongo.update_meeting(first, {"title": "Renamed"})
    assert mongo.get_meeting(first)["title"] == "Renamed"

    assert mongo.delete_meeting(second)
    assert mongo.get_meeting(second) is None
    assert [m["id"] for m in mongo.list_meetings()] == [first]


def test_action_items_are_listed_and_updated_in_place(mongo, sample_meeting):
    meeting_id = mongo.create_meeting(sample_meeting)

    items = mongo.list_action_items()
    assert [(i["id"], i["meeting_title"]) for i in items] == [("a1", "Q3 budget review"), ("a2", "Q3 budget review")]

    assert mongo.update_action_item(meeting_id, "a1", {"status": "Done", "owner": "Priya"})
    updated = {i["id"]: i for i in mongo.get_meeting(meeting_id)["minutes"]["action_items"]}
    assert (updated["a1"]["status"], updated["a1"]["owner"]) == ("Done", "Priya")
    assert updated["a2"]["status"] == "Done" and updated["a2"]["task"].startswith("Update hiring")


def test_invalid_id_raises_database_error(mongo):
    with pytest.raises(mongo.DatabaseError):
        mongo.get_meeting("not-an-object-id")
