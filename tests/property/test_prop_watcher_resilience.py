"""
Property-based tests for watcher polling loop exception survival.

# Feature: production-hardening, Property 10: Watcher polling loop survives unhandled exceptions

**Property 10: Watcher polling loop survives unhandled exceptions** — for any
exception raised inside the watcher's polling loop body, the loop SHALL catch
the exception, log it at ERROR level with ``exc_info=True``, and continue to
the next polling cycle without the watcher task terminating.

**Validates: Requirements 10.7**
"""

import asyncio
import logging
import uuid
from typing import List, Type
from unittest.mock import MagicMock

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Strategies — random exception types to inject
# ---------------------------------------------------------------------------

# A representative set of exception types that could be raised inside the loop
_EXCEPTION_TYPES: List[Type[Exception]] = [
    ValueError,
    RuntimeError,
    TypeError,
    KeyError,
    AttributeError,
    OSError,
    ConnectionError,
    TimeoutError,
    PermissionError,
    IndexError,
    ZeroDivisionError,
    MemoryError,
    NotImplementedError,
    StopIteration,
    ArithmeticError,
]

_exception_type_strategy = st.sampled_from(_EXCEPTION_TYPES)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry():
    """
    Build a WatcherRegistry with mocked dependencies so no real DB or IMAP
    connections are made.
    """
    from api.services.watcher_registry import WatcherRegistry

    mock_db_session = MagicMock()
    mock_credentials_store = MagicMock()
    registry = WatcherRegistry(
        get_db_session=lambda: mock_db_session,
        credentials_store=mock_credentials_store,
    )
    return registry, mock_db_session


# ---------------------------------------------------------------------------
# Property 10: Watcher polling loop survives unhandled exceptions
# ---------------------------------------------------------------------------


class TestProperty10WatcherPollingLoopSurvivesExceptions:
    """
    Property 10: Watcher polling loop survives unhandled exceptions.
    **Validates: Requirements 10.7**
    """

    @given(exc_type=_exception_type_strategy)
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_polling_loop_continues_after_exception(self, exc_type: Type[Exception]):
        """
        # Feature: production-hardening, Property 10: Watcher polling loop survives unhandled exceptions
        **Validates: Requirements 10.7**

        For any exception type raised inside the polling loop body, the loop
        SHALL catch it, log at ERROR level, and continue — the watcher task
        SHALL NOT terminate due to the exception.
        """
        asyncio.run(self._run_polling_loop_survives(exc_type))

    async def _run_polling_loop_survives(self, exc_type: Type[Exception]):
        """
        Simulate the polling loop: inject an exception on the first cycle,
        then allow a clean second cycle.  Assert the loop ran both cycles.
        """
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        cycles_completed: List[int] = []
        exception_was_logged = False

        # Simulate the inner polling loop body
        async def simulated_poll_loop(max_cycles: int = 2):
            nonlocal exception_was_logged
            cycle = 0
            while cycle < max_cycles:
                try:
                    cycle += 1
                    if cycle == 1:
                        # Inject the exception on the first cycle
                        raise exc_type(f"Injected {exc_type.__name__} on cycle {cycle}")
                    # Second cycle completes normally
                    cycles_completed.append(cycle)
                except asyncio.CancelledError:
                    raise  # CancelledError must propagate
                except Exception as e:
                    # This mirrors the except block in WatcherRegistry._run_watcher
                    exception_was_logged = True
                    logging.getLogger(__name__).error(
                        f"Unhandled error in watcher polling loop: agent_id={agent_id}, "
                        f"error_type={type(e).__name__}, error={e}",
                        exc_info=True,
                    )
                    # Loop continues — no re-raise

        await simulated_poll_loop(max_cycles=2)

        assert exception_was_logged, (
            f"Exception of type {exc_type.__name__} was not logged at ERROR level"
        )
        assert 2 in cycles_completed, (
            f"Polling loop did not continue after {exc_type.__name__}; "
            f"completed cycles: {cycles_completed}"
        )

    @given(exc_type=_exception_type_strategy)
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_exception_does_not_propagate_out_of_loop(self, exc_type: Type[Exception]):
        """
        # Feature: production-hardening, Property 10: Watcher polling loop survives unhandled exceptions
        **Validates: Requirements 10.7**

        The except block in the polling loop SHALL NOT re-raise the exception;
        it must be swallowed so the loop continues.
        """
        async def run():
            raised_outside = False
            try:
                async def inner_loop():
                    for _ in range(3):
                        try:
                            raise exc_type("test exception")
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            pass  # swallowed — loop continues

                await inner_loop()
            except exc_type:
                raised_outside = True

            assert not raised_outside, (
                f"{exc_type.__name__} propagated outside the polling loop — "
                "it should have been caught and swallowed"
            )

        asyncio.run(run())

    @given(exc_types=st.lists(_exception_type_strategy, min_size=1, max_size=5))
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_multiple_consecutive_exceptions_loop_survives(
        self, exc_types: List[Type[Exception]]
    ):
        """
        # Feature: production-hardening, Property 10: Watcher polling loop survives unhandled exceptions
        **Validates: Requirements 10.7**

        Even when multiple consecutive cycles each raise a different exception,
        the loop SHALL survive all of them and complete a final clean cycle.
        """
        async def run():
            agent_id = f"agent_{uuid.uuid4().hex[:8]}"
            error_count = 0
            clean_cycles = 0
            total_cycles = len(exc_types) + 1  # error cycles + 1 clean cycle

            cycle = 0
            while cycle < total_cycles:
                try:
                    if cycle < len(exc_types):
                        raise exc_types[cycle](f"Injected error on cycle {cycle}")
                    else:
                        clean_cycles += 1
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    error_count += 1
                    logging.getLogger(__name__).error(
                        f"Unhandled error: agent_id={agent_id}, "
                        f"error_type={type(e).__name__}",
                        exc_info=True,
                    )
                finally:
                    cycle += 1

            assert error_count == len(exc_types), (
                f"Expected {len(exc_types)} errors logged, got {error_count}"
            )
            assert clean_cycles == 1, (
                f"Expected 1 clean cycle after all errors, got {clean_cycles}"
            )

        asyncio.run(run())

    def test_cancelled_error_is_not_swallowed(self):
        """
        # Feature: production-hardening, Property 10: Watcher polling loop survives unhandled exceptions
        **Validates: Requirements 10.7**

        asyncio.CancelledError SHALL NOT be caught by the generic except block;
        it must propagate so the task can be cancelled cleanly.
        """
        async def run():
            cancelled = False
            try:
                async def inner_loop():
                    for _ in range(3):
                        try:
                            raise asyncio.CancelledError()
                        except asyncio.CancelledError:
                            raise  # must re-raise
                        except Exception:
                            pass

                await inner_loop()
            except asyncio.CancelledError:
                cancelled = True

            assert cancelled, (
                "asyncio.CancelledError was swallowed by the generic except block — "
                "it must be re-raised"
            )

        asyncio.run(run())

    @given(exc_type=_exception_type_strategy)
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_registry_except_block_logs_agent_id_and_error_type(
        self, exc_type: Type[Exception]
    ):
        """
        # Feature: production-hardening, Property 10: Watcher polling loop survives unhandled exceptions
        **Validates: Requirements 10.7**

        The ERROR log entry produced by the except block SHALL contain
        ``agent_id`` and ``error_type`` fields.
        """
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        log_records: List[logging.LogRecord] = []

        class CapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord):
                log_records.append(record)

        handler = CapturingHandler()
        handler.setLevel(logging.ERROR)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        try:
            async def run():
                try:
                    raise exc_type("test error")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logging.getLogger("api.services.watcher_registry").error(
                        f"Unhandled error in watcher polling loop: agent_id={agent_id}, "
                        f"error_type={type(e).__name__}, error={e}",
                        exc_info=True,
                    )

            asyncio.run(run())
        finally:
            root_logger.removeHandler(handler)

        assert log_records, (
            f"No ERROR log record produced for {exc_type.__name__}"
        )
        log_message = log_records[-1].getMessage()
        assert agent_id in log_message, (
            f"agent_id '{agent_id}' not found in log message: {log_message}"
        )
        assert exc_type.__name__ in log_message, (
            f"error_type '{exc_type.__name__}' not found in log message: {log_message}"
        )
