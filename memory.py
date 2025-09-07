"""
@file memory.py
@brief Simple in-memory storage for workflow results and intermediate data.
"""

MEMORY = {}


def get_memory(key: str):
    """
    Retrieves a value from memory.

    @param key Memory key
    @return Stored value or None if not found
    """
    return MEMORY.get(key)


def set_memory(key: str, value: str):
    """
    Stores a value in memory.

    @param key Memory key
    @param value Value to store
    """
    MEMORY[key] = value