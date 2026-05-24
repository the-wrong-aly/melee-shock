_registry: dict[str, tuple[type, type]] = {}
# name -> (ModeClass, ConfigClass)


def register_mode(name: str):
    def decorator(cls):
        # expect each mode module to define a paired Config class
        config_cls = cls.Config
        _registry[name] = (cls, config_cls)
        return cls

    return decorator


def get(name: str):
    if name not in _registry:
        raise ValueError(f"Unknown mode: {name!r}. Available: {list(_registry)}")
    return _registry[name]
