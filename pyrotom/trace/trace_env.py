from .trace_events import TRACE_EVENTS
from .hook import EventHook


class TraceEnv(EventHook):
    def _build_trace_func(self):
        def trace(frame, event, arg):
            if event in TRACE_EVENTS:
                self._execute_hook(event, frame, arg)
            self._old_trace_func = self._old_trace_func(frame, event, arg)
            return self._new_trace_func
        return trace

    def __enter__(self):
        self._old_trace_func = sys.gettrace()
        self._new_trace_func = self._build_trace_func(self)
        sys.settrace(self._new_trace_func)
        return self._new_trace_func

    def __exit__(self, type, value, trace):
        sys.settrace(self._old_trace_func)
        self._old_trace_func = None
        self._new_trace_func = None
