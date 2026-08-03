from uuid import UUID

from auto_trading_v2.domain.paper_orders import internal_paper_broker_reference
from auto_trading_v2.domain.primitives import ClientOrderID


def test_internal_reference_is_exact_stable_and_bounded() -> None:
    first = ClientOrderID(UUID("10000000-0000-0000-0000-000000000001"))
    second = ClientOrderID(UUID("10000000-0000-0000-0000-000000000002"))

    reference = internal_paper_broker_reference(first)

    assert reference == f"internal-paper:v1:{first.serialize()}"
    assert reference == internal_paper_broker_reference(first)
    assert reference != internal_paper_broker_reference(second)
    assert not any(character.isspace() for character in reference)
    assert len(reference) <= 160
