"""Custom exceptions for the RPX application."""


class RPXError(Exception):
    """Base exception for all RPX errors."""

    pass


class PathNotFoundError(RPXError):
    """Raised when the specified project path does not exist."""

    pass


class ScanError(RPXError):
    """Raised when a non-recoverable error occurs during project scanning."""

    pass


class ConfigError(RPXError):
    """Raised when an invalid configuration is encountered."""

    pass


class ExportError(RPXError):
    """Raised when an export operation fails (e.g. file exists without overwrite)."""

    pass


class GitError(RPXError):
    """Raised when an error occurs while interacting with Git."""

    pass
