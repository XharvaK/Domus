# Amendment A16

| A16 | §5 motive read (schema unchanged, still v4) | Probe 2.3.3: a live commodity's stored value is `inst._value` (`BaseStatistic.get_value` offset 10 after `ContinuousStatistic.get_value` offset 10 updates). `default_value` is not used for an instance. `_modified_value` is not on the Commodity chain. | 1.128 bytecode: `Statistic._update_modified_value` offset 64 is the only store of `_modified_value`, and `Statistic` subclasses `BaseStatistic` beside `ContinuousStatistic`. L0 re-check 2.3.2: `motive_diag.stage = row_error:_modified_value`. |
