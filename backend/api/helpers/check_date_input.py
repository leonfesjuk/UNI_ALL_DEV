
from datetime import date, timedelta
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .loger import init_logger

my_logger = init_logger()



class CostomInput(BaseModel):
    date_start: date
    date_finish: date
    days_of_order: int | None = Field(default=None, description="Кількість днів для замовлення за замовчуванням")
   
class Costom_input_with_groups(CostomInput):
    groups: list[str] = Field(default=None, description="Список груп товарів для замовлення")
    markets: list[str] = Field(default_factory=list, description="Список магазинів для замовлення")
    today_stocs_mode: bool = Field(default=False, description="Використовувати залишки на сьогодні") # New field

    class Config:
        schema_extra = {
            "example": {
                "date_start": "2024-10-01",
                "date_finish": "2024-12-01",
                "days_of_order": 30,
                "groups": ["group1", "group2"],
                "markets": ["market1", "market2"]
            }
        }
    
def checking_dates_input(input_data: CostomInput, days_of_order):
    my_logger.debug("Checking dates input")
    date_start = input_data.date_start
    date_finish = input_data.date_finish
    days_of_order = input_data.days_of_order
    

    
    if date_start is None:
        my_logger.debug("Start date is missing.")
        return JSONResponse(
            status_code=400,
            content={"detail": "Start date is required."}
        )
    if date_finish is None:
        my_logger.debug("Finish date is missing.")
        return JSONResponse(
            status_code=400,
            content={"detail": "Finish date is required."}
        )

    # Перевірка, чи date_finish пізніше date_start
    if date_finish <= date_start:
        my_logger.debug("Finish date must be after start date.")
        return JSONResponse(
            status_code=400,
            content={"detail": "Finish date must be after start date."}
        )

    # Перевірка, чи date_finish не є в майбутньому, з урахуванням today_stocs_mode
    # Якщо today_stocs_mode = True, то date_finish може бути сьогоднішньою датою.
    # В іншому випадку (today_stocs_mode = False або відсутній), date_finish має бути до сьогоднішньої дати.
    if isinstance(input_data, Costom_input_with_groups) and input_data.today_stocs_mode:
        if date_finish > date.today():
            my_logger.debug("Finish date cannot be in the future when today_stocs_mode is enabled.")
            return JSONResponse(
                status_code=400,
                content={"detail": "Finish date cannot be in the future."}
            )
    else: # Default behavior: date_finish must be before today
        if date_finish >= date.today():
            my_logger.debug("Finish date cannot be today or in the future without today_stocs_mode.")
            return JSONResponse(
                status_code=400,
                content={"detail": "Finish date cannot be today or in the future."}
            )

    # Перевірка days_of_order
    # 'days_of_order' parameter to the function is the minimum required days,
    # 'input_data.days_of_order' is the actual value from the user.
    if input_data.days_of_order is not None:
        if input_data.days_of_order < days_of_order: # Corrected comparison
            my_logger.debug(f"Days of order must be at least {days_of_order}.")
            return JSONResponse(
                status_code=400,
                content={"detail": f"Days of order must be at least {days_of_order}."}
            )
    elif days_of_order is not None: # If input_data.days_of_order is None, but a min_days is required
        my_logger.debug("Days of order is required but not provided.")
        return JSONResponse(
                status_code=400,
                content={"detail": "Days of order is required."}
            )
    else:
        my_logger.debug("days_of_order validation skipped as not required.")

    if isinstance(input_data, Costom_input_with_groups) and input_data.groups is not None:
        if not input_data.groups:
            my_logger.error("groups list cannot be empty")
            return JSONResponse(
                status_code=400,
                content={"detail": "groups list cannot be empty"}
            )
        for group in input_data.groups:
            if not isinstance(group, str) or not group.strip():
                my_logger.error("All groups must be non-empty strings")
                raise ValueError("All groups must be non-empty strings")
        for market in input_data.markets:
            if not market.strip():
                my_logger.error(f"Market '{market}' is an empty or whitespace-only string.")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "All markets must be non-empty strings."}
                )

    
    
    # Якщо всі перевірки пройдено
    return input_data

