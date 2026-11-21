from .sources import ArbeitnowAdapter, GreenhouseAdapter, LeverAdapter, RemotiveAdapter

ADAPTERS = {a.slug: a for a in (RemotiveAdapter(), ArbeitnowAdapter(), GreenhouseAdapter(), LeverAdapter())}
