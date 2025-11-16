"""
Parallel processing utilities for ADAPT framework.

Provides utilities for processing signals and running operations
in parallel to improve performance.
"""

import asyncio
from typing import List, Callable, Any, TypeVar
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class ParallelProcessor:
    """
    Process items in parallel using async concurrency or thread/process pools.
    """

    def __init__(self, max_workers: int = 4):
        """
        Initialize parallel processor.

        Args:
            max_workers: Maximum number of workers for thread/process pools
        """
        self.max_workers = max_workers
        self.thread_executor = ThreadPoolExecutor(max_workers=max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=max_workers)

    async def map_async(
        self,
        items: List[T],
        func: Callable[[T], R],
        max_concurrent: int = 10
    ) -> List[R]:
        """
        Map an async function over items with concurrency control.

        Args:
            items: Items to process
            func: Async function to apply to each item
            max_concurrent: Maximum number of concurrent operations

        Returns:
            List of results in same order as input items
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(item: T) -> R:
            async with semaphore:
                return await func(item)

        tasks = [process_with_semaphore(item) for item in items]
        return await asyncio.gather(*tasks)

    async def map_threaded(
        self,
        items: List[T],
        func: Callable[[T], R]
    ) -> List[R]:
        """
        Map a sync function over items using thread pool.

        Useful for I/O-bound operations that don't have async support.

        Args:
            items: Items to process
            func: Sync function to apply to each item

        Returns:
            List of results in same order as input items
        """
        loop = asyncio.get_event_loop()

        tasks = [
            loop.run_in_executor(self.thread_executor, func, item)
            for item in items
        ]

        return await asyncio.gather(*tasks)

    async def map_processes(
        self,
        items: List[T],
        func: Callable[[T], R]
    ) -> List[R]:
        """
        Map a function over items using process pool.

        Useful for CPU-bound operations. The function must be picklable.

        Args:
            items: Items to process
            func: Function to apply to each item

        Returns:
            List of results in same order as input items
        """
        loop = asyncio.get_event_loop()

        tasks = [
            loop.run_in_executor(self.process_executor, func, item)
            for item in items
        ]

        return await asyncio.gather(*tasks)

    async def process_batches(
        self,
        items: List[T],
        processor: Callable[[List[T]], List[R]],
        batch_size: int = 100,
        max_concurrent_batches: int = 4
    ) -> List[R]:
        """
        Process items in batches with concurrency control.

        Args:
            items: Items to process
            processor: Async function that processes a batch
            batch_size: Number of items per batch
            max_concurrent_batches: Maximum number of batches to process concurrently

        Returns:
            List of all results
        """
        # Split into batches
        batches = [
            items[i:i + batch_size]
            for i in range(0, len(items), batch_size)
        ]

        logger.info(f"Processing {len(items)} items in {len(batches)} batches")

        # Process batches with concurrency control
        semaphore = asyncio.Semaphore(max_concurrent_batches)

        async def process_batch_with_semaphore(batch: List[T]) -> List[R]:
            async with semaphore:
                if asyncio.iscoroutinefunction(processor):
                    return await processor(batch)
                else:
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(self.thread_executor, processor, batch)

        tasks = [process_batch_with_semaphore(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks)

        # Flatten results
        results = []
        for batch_result in batch_results:
            results.extend(batch_result)

        return results

    def shutdown(self):
        """Shutdown thread and process pools"""
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)


# Global processor instance
_processor = ParallelProcessor()


def get_parallel_processor() -> ParallelProcessor:
    """Get the global parallel processor instance"""
    return _processor
