// Reads. Business users and the copilot may read batches; claim reads are scoped.

@id("business-read-batch")
permit (principal is OAE::BusinessUser, action == OAE::Action::"ReadBatch", resource is OAE::Batch);

@id("copilot-read-batch")
permit (principal is OAE::Copilot, action == OAE::Action::"ReadBatch", resource is OAE::Batch);

@id("auditor-read-claim")
permit (principal is OAE::BusinessUser, action == OAE::Action::"ReadClaim", resource is OAE::Claim)
when { principal.role == "AUDITOR" };

@id("recycler-read-own-claim")
permit (principal is OAE::BusinessUser, action == OAE::Action::"ReadClaim", resource is OAE::Claim)
when { principal.role == "RECYCLER" && resource.recycler_party_id == principal.party_id };

@id("producer-read-citing-claim")
permit (principal is OAE::BusinessUser, action == OAE::Action::"ReadClaim", resource is OAE::Claim)
when { principal.role == "PRODUCER" && resource.producer_party_ids.contains(principal.party_id) };

@id("copilot-read-claim")
permit (principal is OAE::Copilot, action == OAE::Action::"ReadClaim", resource is OAE::Claim);

// P7: the copilot is read-only. Any action in the Write group is denied.
@id("copilot-never-writes")
forbid (principal is OAE::Copilot, action in OAE::Action::"Write", resource);
