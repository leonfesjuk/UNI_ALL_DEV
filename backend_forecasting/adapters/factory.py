from config.settings import Settings
from core.gateway.i_data_gateway import DataInputGateway
from core.ports.output import AIPort


def create_data_adapter(
    settings: Settings,
    start_date,
    end_date,
    shop_id: int | None = None,
) -> DataInputGateway:
    match settings.data_adapter:
        case "erp":
            from adapters.secondary.data.erp_gateway import (
                ErpDataInputGateway,
            )
            return ErpDataInputGateway(start_date, end_date, shop_id=shop_id)
        case "fake":
            from adapters.secondary.data.fake_adapter import (
                FakeDataAdapter,
            )
            return FakeDataAdapter()
        case _:
            raise ValueError(f"Unknown data adapter: {settings.data_adapter}")


def create_ai_adapter(settings: Settings) -> AIPort:
    match settings.ai_adapter:
        case "fallback":
            from adapters.secondary.ai.fallback_adapter import (
                FallbackAdapter,
            )
            return FallbackAdapter()
        case "kronos":
            from adapters.secondary.ai.kronos_adapter import (
                KronosAdapter,
            )
            return KronosAdapter(settings.model_path)
        case _:
            raise ValueError(f"Unknown AI adapter: {settings.ai_adapter}")
