# python/repo_manager.py
"""
Repository manager for multi-repo vibe operations.

Manages a list of git repositories that vibe can operate on.
Repos are stored in memory with an optional JSON file for persistence.
"""

import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class RepoConfig:
    """Configuration for a connected git repository."""

    id: str
    name: str
    path: str
    is_default: bool = False


@dataclass
class RepoManager:
    """
    Manages configured git repositories.

    Stores repos in memory with optional file persistence.
    """

    repos: list[RepoConfig] = field(default_factory=list)
    _config_path: Optional[Path] = None

    def __post_init__(self):
        # Load from config file if it exists
        config_dir = Path(os.environ.get("VIBE_CONFIG_DIR", Path.home() / ".vibe-remote"))
        config_dir.mkdir(parents=True, exist_ok=True)
        self._config_path = config_dir / "repos.json"

        if self._config_path.exists():
            self._load()

    def _load(self) -> None:
        """Load repos from config file."""
        try:
            with open(self._config_path, "r") as f:
                data = json.load(f)
                self.repos = [RepoConfig(**r) for r in data.get("repos", [])]
        except Exception as e:
            print(f"[RepoManager] Failed to load config: {e}")

    def _save(self) -> None:
        """Save repos to config file."""
        try:
            data = {"repos": [vars(r) for r in self.repos]}
            with open(self._config_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[RepoManager] Failed to save config: {e}")

    def list_repos(self) -> list[RepoConfig]:
        """Get all configured repositories."""
        return self.repos

    def get_repo(self, repo_id: str) -> Optional[RepoConfig]:
        """Get a repo by ID."""
        for repo in self.repos:
            if repo.id == repo_id:
                return repo
        return None

    def get_default_repo(self) -> Optional[RepoConfig]:
        """Get the default repository."""
        for repo in self.repos:
            if repo.is_default:
                return repo
        # Return first repo if no default set
        return self.repos[0] if self.repos else None

    def add_repo(self, path: str, name: Optional[str] = None) -> RepoConfig:
        """
        Add a new repository.

        Args:
            path: Path to the git repository
            name: Display name (auto-detected from path if not provided)

        Returns:
            The created RepoConfig

        Raises:
            ValueError: If path is not a valid git repo or already exists
        """
        # Normalize and validate path
        repo_path = Path(path).expanduser().resolve()

        if not repo_path.exists():
            raise ValueError(f"Path does not exist: {repo_path}")

        if not (repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")

        # Check for duplicates
        for repo in self.repos:
            if Path(repo.path).resolve() == repo_path:
                raise ValueError(f"Repository already configured: {repo.name}")

        # Auto-detect name from directory or git remote
        if not name:
            name = self._detect_repo_name(repo_path)

        repo = RepoConfig(
            id=str(uuid.uuid4()),
            name=name,
            path=str(repo_path),
            is_default=len(self.repos) == 0,  # First repo is default
        )

        self.repos.append(repo)
        self._save()
        return repo

    def remove_repo(self, repo_id: str) -> bool:
        """Remove a repository by ID."""
        for i, repo in enumerate(self.repos):
            if repo.id == repo_id:
                was_default = repo.is_default
                del self.repos[i]

                # If removed repo was default, set new default
                if was_default and self.repos:
                    self.repos[0].is_default = True

                self._save()
                return True
        return False

    def set_default(self, repo_id: str) -> bool:
        """Set a repository as the default."""
        found = False
        for repo in self.repos:
            if repo.id == repo_id:
                repo.is_default = True
                found = True
            else:
                repo.is_default = False

        if found:
            self._save()
        return found

    def _detect_repo_name(self, repo_path: Path) -> str:
        """Try to detect a good name for the repository."""
        # Try to get name from git remote
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Extract repo name from URL
                # e.g., git@github.com:user/repo.git -> repo
                # e.g., https://github.com/user/repo.git -> repo
                name = url.split("/")[-1]
                if name.endswith(".git"):
                    name = name[:-4]
                if name:
                    return name
        except Exception:
            pass

        # Fall back to directory name
        return repo_path.name


# Singleton instance
_repo_manager: Optional[RepoManager] = None


def get_repo_manager() -> RepoManager:
    """Get or create the singleton RepoManager."""
    global _repo_manager
    if _repo_manager is None:
        _repo_manager = RepoManager()
    return _repo_manager
