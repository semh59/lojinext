"""Event surface of the admin_platform module.

admin_platform does not publish or listen to any ``v2.modules.platform_infra.events
.event_bus.EventType`` domain event — it has no ``EventType`` entries of its
own and no ``@publishes``/handler wiring.

It DOES use a separate, lower-level mechanism: ``update_config``
(``application/konfig_service.py``) publishes to the raw Redis pub/sub
channel ``"config_updates"`` via ``get_pubsub_manager()`` so multi-worker
deployments pick up a config change without waiting for the 1-hour cache
TTL. This is intentionally NOT routed through the domain event bus — it is
cache-invalidation plumbing, not a business event other modules react to.
"""
