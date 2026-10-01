import pytest

ANA, BEN = "user-ana", "user-ben"


def test_create_get_list_update_delete(mongo, sample_meeting):
    first = mongo.create_meeting(sample_meeting, ANA)
    second = mongo.create_meeting(dict(sample_meeting, title="Later meeting", meeting_date="2026-09-25"), ANA)

    listed = mongo.list_meetings(ANA)
    assert [m["title"] for m in listed] == ["Later meeting", "Q3 budget review"]
    assert "transcript" not in listed[0]

    loaded = mongo.get_meeting(first, ANA)
    assert loaded["id"] == first and loaded["minutes"]["summary"].startswith("The team reviewed")

    assert mongo.update_meeting(first, ANA, {"title": "Renamed"})
    assert mongo.get_meeting(first, ANA)["title"] == "Renamed"

    assert mongo.delete_meeting(second, ANA)
    assert mongo.get_meeting(second, ANA) is None
    assert [m["id"] for m in mongo.list_meetings(ANA)] == [first]


def test_meetings_are_private_to_their_owner(mongo, sample_meeting):
    meeting_id = mongo.create_meeting(sample_meeting, ANA)

    assert mongo.list_meetings(BEN) == [] and mongo.list_action_items(BEN) == []
    assert mongo.get_meeting(meeting_id, BEN) is None
    assert not mongo.update_meeting(meeting_id, BEN, {"title": "Hacked"})
    assert not mongo.update_action_item(meeting_id, BEN, "a1", {"status": "Done"})
    assert not mongo.delete_meeting(meeting_id, BEN)
    assert mongo.get_meeting(meeting_id, ANA)["title"] == "Q3 budget review"

    assert mongo.delete_meetings_of(ANA) == [meeting_id]
    assert mongo.list_meetings(ANA) == []


def test_unowned_meetings_can_be_claimed_once(mongo, sample_meeting):
    legacy = str(mongo.get_collection().insert_one(dict(sample_meeting)).inserted_id)
    assert mongo.claim_unowned_meetings(ANA) == 1
    assert mongo.claim_unowned_meetings(BEN) == 0
    assert mongo.get_meeting(legacy, ANA) is not None and mongo.get_meeting(legacy, BEN) is None


def test_action_items_are_listed_and_updated_in_place(mongo, sample_meeting):
    meeting_id = mongo.create_meeting(sample_meeting, ANA)

    items = mongo.list_action_items(ANA)
    assert [(i["id"], i["meeting_title"]) for i in items] == [("a1", "Q3 budget review"), ("a2", "Q3 budget review")]

    assert mongo.update_action_item(meeting_id, ANA, "a1", {"status": "Done", "owner": "Priya"})
    updated = {i["id"]: i for i in mongo.get_meeting(meeting_id, ANA)["minutes"]["action_items"]}
    assert (updated["a1"]["status"], updated["a1"]["owner"]) == ("Done", "Priya")
    assert updated["a2"]["status"] == "Done" and updated["a2"]["task"].startswith("Update hiring")


def test_invalid_id_raises_database_error(mongo):
    with pytest.raises(mongo.DatabaseError):
        mongo.get_meeting("not-an-object-id", ANA)
