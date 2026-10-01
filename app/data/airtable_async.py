# Run blocking Airtable calls off the event loop.

import asyncio
import contextvars
import functools
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="airtable")


async def run_airtable(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    ctx = contextvars.copy_context()
    call = functools.partial(ctx.run, func, *args, **kwargs)
    return await loop.run_in_executor(_executor, call)


def shutdown_executor():
    import concurrent.futures.thread as cft

    _executor.shutdown(wait=False, cancel_futures=True)
    for thread in list(_executor._threads):
        cft._threads_queues.pop(thread, None)
