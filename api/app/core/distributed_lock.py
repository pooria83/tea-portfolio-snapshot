"""Redis distributed lock with owner tokens and atomic compare-and-del release."""

import uuid

from redis.asyncio import Redis

_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


def new_lock_token() -> str:
    return str(uuid.uuid4())


async def acquire_lock(redis: Redis, key: str, ttl: int, token: str | None = None) -> str | None:
    """Try to acquire a lock with SET NX EX. Returns the owner token on success."""
    token = token or new_lock_token()
    result = await redis.set(key, token, nx=True, ex=ttl)
    if result is not None:
        return token
    return None


async def release_lock(redis: Redis, key: str, token: str) -> None:
    """Release the lock only if we still own it (atomic compare-and-del)."""
    try:
        await redis.eval(_RELEASE_LUA, 1, key, token)
    except Exception:
        await redis.delete(key)
