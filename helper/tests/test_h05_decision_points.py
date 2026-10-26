"""H0.5 (plans): the courier keeps how many plan steps Ashley still holds. The decision points that
woke her were removed with the thalamus decision (D2); the bridge sends every change now."""

from domus_helper.acts import ActCourier
from domus_helper.spool import Spool


class _Sync:
    def __init__(self, planned):
        self.planned = planned

    def sync_acts(self, body):
        return {"status": "ok", "applied": 0, "acts": [], **({} if self.planned is None else {"planned": self.planned})}


def test_the_courier_remembers_how_many_plan_steps_ashley_still_holds(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    courier = ActCourier(spool, lambda command, args: None)
    assert courier.planned == 0
    courier.tick(_Sync(2), "h", 1_000, True)
    assert courier.planned == 2
    assert ActCourier(spool, lambda command, args: None).planned == 2
    courier.tick(_Sync(None), "h", 2_000, True)  # an Ashley without plans
    assert courier.planned == 0
    courier.tick(_Sync("x"), "h", 3_000, True)
    assert courier.planned == 0
