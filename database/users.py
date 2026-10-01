# database/users.py
"""
User accounts (collection "users").

Document shape:
    email (unique, lowercase), name, password_hash, token_version,
    created_at, updated_at, last_login_at

`token_version` goes up whenever the password changes or the user signs out
everywhere; sign-in tokens carry the version they were issued with, so older
tokens stop working.
"""
import logging
import secrets

from pymongo.errors import DuplicateKeyError, PyMongoError

from database.mongodb import DatabaseError, _now, _object_id, _run, get_database

logger = logging.getLogger(__name__)

_indexes_ready = False


class EmailTaken(Exception):
    """An account with this email already exists"""


def get_collection():
    global _indexes_ready
    collection = get_database()["users"]
    if not _indexes_ready:
        # The unique index is what stops two accounts sharing an email, so failures here are real errors
        _run(lambda: collection.create_index("email", unique=True), "preparing the accounts table")
        _indexes_ready = True
    return collection


def public_user(doc):
    """The fields that are safe to send to the browser"""
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
        "name": doc.get("name") or "",
        "created_at": doc.get("created_at"),
    }


def count_users():
    return _run(lambda: get_collection().count_documents({}), "counting accounts")


def create_user(email, name, password_hash):
    """
    Insert an account

    Returns:
        dict: The stored document

    Raises:
        EmailTaken: An account with this email already exists
    """
    doc = {"email": email, "name": name, "password_hash": password_hash, "token_version": 0,
           "created_at": _now(), "updated_at": _now(), "last_login_at": _now()}
    try:
        result = get_collection().insert_one(doc)
    except DuplicateKeyError as e:
        raise EmailTaken(email) from e
    except PyMongoError as e:
        logger.exception("MongoDB error while creating an account")
        raise DatabaseError(f"Database error while creating the account: {e}") from e
    return dict(doc, _id=result.inserted_id)


def get_user(user_id):
    """The account, or None when the id is unknown or malformed"""
    try:
        oid = _object_id(user_id, "user")
    except DatabaseError:
        return None
    return _run(lambda: get_collection().find_one({"_id": oid}), "loading the account")


def find_user_by_email(email):
    return _run(lambda: get_collection().find_one({"email": email}), "loading the account")


def update_user(user_id, fields):
    oid = _object_id(user_id, "user")
    update = dict(fields, updated_at=_now())
    _run(lambda: get_collection().update_one({"_id": oid}, {"$set": update}), "updating the account")
    return get_user(user_id)


def record_login(user_id):
    oid = _object_id(user_id, "user")
    _run(lambda: get_collection().update_one({"_id": oid}, {"$set": {"last_login_at": _now()}}), "updating the account")


def end_sessions(user_id, password_hash=None):
    """
    Sign the user out everywhere (optionally setting a new password at the same time)

    Returns:
        dict: The updated account
    """
    oid = _object_id(user_id, "user")
    fields = {"updated_at": _now()}
    if password_hash:
        fields["password_hash"] = password_hash
    _run(lambda: get_collection().update_one({"_id": oid}, {"$set": fields, "$inc": {"token_version": 1}}),
         "updating the account")
    return get_user(user_id)


def delete_user(user_id):
    oid = _object_id(user_id, "user")
    return _run(lambda: get_collection().delete_one({"_id": oid}), "deleting the account").deleted_count > 0


def load_or_create_secret():
    """
    The key that signs sign-in tokens when AUTH_SECRET isn't set: created once
    and kept in the database, so sessions survive restarts and every server
    process agrees on it

    Returns:
        bytes
    """
    config = get_database()["app_config"]

    def load():
        config.update_one({"_id": "auth_secret"}, {"$setOnInsert": {"value": secrets.token_hex(32)}}, upsert=True)
        return bytes.fromhex(config.find_one({"_id": "auth_secret"})["value"])
    return _run(load, "loading the sign-in key")
