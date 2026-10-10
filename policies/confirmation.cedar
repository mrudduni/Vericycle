// Only a handler-confirmation token may add HANDLER to confirmed_by_roles,
// only on the one event it was issued for, and only for the fields it was issued for.

@id("handler-token-confirms-own-event")
permit (principal is OAE::HandlerToken, action == OAE::Action::"ConfirmHandlerField", resource is OAE::Event)
when {
  principal.batch_id == resource.batch_id &&
  principal.seq == resource.seq &&
  principal.field_names.containsAll(context.field_names)
};

@id("only-handler-tokens-confirm")
forbid (principal, action == OAE::Action::"ConfirmHandlerField", resource)
unless { principal is OAE::HandlerToken };
