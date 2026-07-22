import logging

from redis.exceptions import ConnectionError as RedisConnectionError  # type: ignore
from redis.exceptions import TimeoutError as RedisTimeoutError  # type: ignore

logger = logging.getLogger(__name__)


class SuppressDisconnectErrors:
    """
    Hide the channel layer teardown noise that follows an ordinary client hangup.

    When a tab closes, Channels runs the consumer's disconnect() and raises
    StopConsumer. On the way out, await_many_dispatch() cancels the pending
    channel layer read, which is parked inside redis-py's asyncio.timeout()
    block waiting on BZPOPMIN. asyncio turns that cancellation into a plain
    TimeoutError and redis-py re-raises it as redis.exceptions.TimeoutError.
    Channels only catches asyncio.CancelledError there, so the redis error
    replaces the StopConsumer and uvicorn logs a full traceback for what is
    just someone leaving the page.

    The error is only swallowed once the client has actually sent
    websocket.disconnect. A redis failure on a live connection still
    propagates, so genuine outages stay visible in the logs.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'websocket':
            return await self.app(scope, receive, send)

        client_gone = False

        async def receive_watching_for_hangup():
            nonlocal client_gone
            message = await receive()
            if message.get('type') == 'websocket.disconnect':
                client_gone = True
            return message

        try:
            return await self.app(scope, receive_watching_for_hangup, send)
        except (RedisTimeoutError, RedisConnectionError) as exc:
            if not client_gone:
                raise
            logger.debug(f"Channel layer read cancelled on disconnect for {scope.get('path')}: {exc}")
