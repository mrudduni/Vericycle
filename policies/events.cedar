// Who may create which ledger event type (CONTRACT §3 EventType, SHAURYA.md 3.8).

@id("collector-create")
permit (principal is OAE::BusinessUser, action == OAE::Action::"CreateEvent", resource is OAE::Batch)
when { principal.role == "COLLECTOR" && ["HANDOVER", "TRANSFER", "CORRECTION"].contains(context.event_type) };

@id("aggregator-create")
permit (principal is OAE::BusinessUser, action == OAE::Action::"CreateEvent", resource is OAE::Batch)
when { principal.role == "AGGREGATOR" && ["TRANSFER", "SPLIT", "MERGE", "CORRECTION"].contains(context.event_type) };

@id("recycler-create")
permit (principal is OAE::BusinessUser, action == OAE::Action::"CreateEvent", resource is OAE::Batch)
when { principal.role == "RECYCLER" && ["INTAKE", "PROCESS", "OUTPUT", "CORRECTION"].contains(context.event_type) };

// P5: a buyer can never record the handler's confirmation, through the API or the UI.
@id("no-business-handler-confirmation")
forbid (principal is OAE::BusinessUser, action == OAE::Action::"CreateEvent", resource)
when { context.confirmed_by_roles.contains("HANDLER") };
