
from pathlib import Path


class DB:
    @staticmethod
    def __raw_user_path(username) -> Path:
        if ".." in username or "/" in username or "\\" in username:
            raise ValueError(f"Invalid username: {username}")
        return Path("./repos").resolve() / username

    @staticmethod
    def __validate_path(username: str, path: str) -> Path:
        # Validate repo parameter - no path traversal allowed
        if ".." in path or path.startswith("/"):
            raise ValueError(f"Invalid repository name: {path}")
        
        # Ensure the resolved path is within the user's directory
        full_path = DB.__raw_user_path(username) / path
        if not full_path.resolve().as_posix().startswith(DB.__raw_user_path(username).as_posix()):
            raise ValueError(f"Access denied: path outside user directory")
        return full_path

    @staticmethod
    def get_user_path(username: str) -> Path:
        """Get local path of user's folder"""
        return DB.__validate_path(username, "")
        
    @staticmethod
    def get_repo_path(username: str, repo: str) -> Path:
        """Get local path of user's repository with security validation"""
        return DB.__validate_path(username, repo)
    
    @staticmethod
    def get_journal_path(username: str, journal: str) -> Path:
        """Get local path of user's journal with security validation"""
        return DB.__validate_path(username, journal)
