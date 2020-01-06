from .trace_events import TRACE_EVENTS


class EventHook(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event_hooks = {event: set() for event in TRACE_EVENTS}

    def add_hook(self, event, hook):
        self.event_hooks[event].add(hook)

    def del_hook(self, event, hook):
        self.event_hooks[event].remove(hook)

    def _execute_hook(self, event, *args, **kwargs):
        for hook in self.event_hooks[event]:
            hook(*args, **kwargs)

    # human interfaces
    for event in TRACE_EVENTS:
        name = f'add_hook_{event}'
        def interface(self, hook):
            return self.add_hook(event, hook)
        locals()[name] = interface
    del event, name, interface
