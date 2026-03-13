import hashlib

# Seed credentials — used only to populate the DB on first startup.
# Passwords are stored as SHA-256 hashes in the database.
USERS = {
    "prutha":  "test123",
    "lavanya": "test123",
    "subbu":   "test123",
    "ansari":  "test123",
}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash
