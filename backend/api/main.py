import sys
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date, datetime, timedelta
import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve
import json
import logging
import time
from sqlalchemy import exc as sa_exc
import io
from fastapi.responses import JSONResponse, StreamingResponse
import pandas as pd
from api.helpers.loger import init_logger
from api.helpers.check_date_input import CostomInput,Costom_input_with_groups, checking_dates_input
from api.helpers.xlsx_maker import create_xlsx_files_ziped
from typing import List, Optional

from redistribution.api_handler import redistribution_api_handler
from redistribution.helpers.category_hierarchy import get_category_hierarchy_tree
from redistribution.helpers.excel_exporter import format_redistribution_plan

from autoorder.analysis import sdp, promotions
from out_product.out_prod  import analyze_out_products
from out_product.market_down_products import market_down_products_generate
from out_product.archive_products import archive_products_analise
from autoorder.conections import category, shop_name, warhause_id, warhauses_smal
from autoorder_m.healpers.base_table import base_table_creation 
from autoorder_m.healpers.category_maker import create_groups_list
from autoorder_m.autoorder_markets import auto_order_markets_start
from dotenv import load_dotenv
from sales_looses.sales_loose import sales_loose_analysis
from insurance_balance.insure_balance_class import Insure_Balance
from insurance_balance.insure_balance_builder import insure_balance_builder
from prices.service.table_creation import prices_with_stocks

from adapters.primary.api import router as forecast_router

basedir = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(basedir, '..', 'frontend', '.env')
load_dotenv(dotenv_path=dotenv_path)
domen_api = os.getenv('DOMEN_API')

my_logger = init_logger()
my_logger.debug("Логер ініціалізований у main.py")
# Add the parent directory to the Python path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Go up TWO levels to ERP-UNI
sys.path.insert(0, project_root)  # Add ERP-UNI to PYTHONPATH
#from autoorder.autoorder import auto_order_w_start
sys.path.insert(1, os.path.join(project_root, 'backend'))

from autoorder.autoorder import auto_order_w_start
########################
#x,y = auto_order_w_start(date(2024,10,1), date(2024,12,10),30)

#print(x.head())

##########################


# Configure logging
#logging.basicConfig(level=logging.DEBUG)
#logger = logging.getLogger(__name__)

# Initialize FastAPI app

app = FastAPI()
origins = [
    "http://localhost",
    "http://localhost:8000",
    domen_api,
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forecast_router)

# Create asyncio Lock for auto_order process
auto_order_lock = asyncio.Lock()

# Define input model for auto order
class AutoOrderInput(BaseModel):
    date_start: date
    date_finish: date
    days_of_order: int

# Define input model for redistribution plan generation
class RedistributionInput(BaseModel):
    date_start: date
    date_finish: date
    days_of_analysis: int
    min_surplus_coefficient: float
    donor_markets_ids: List[str]
    recipient_markets_ids: List[str]
    selected_lowest_categories_names: Optional[List[str]] = None  # Changed from IDs to names
    today_stocs_mode: bool = False



async def execute_auto_order_with_retries(input_data, max_retries=5):
    try:
        for attempt in range(max_retries):
            try:
                result_table, mid_table = auto_order_w_start(
                    date_start=input_data.date_start,
                    date_finish=input_data.date_finish,
                    days_of_order=input_data.days_of_order
                )
                return result_table, mid_table
            except sa_exc.SQLAlchemyError as e:
                if attempt < max_retries - 1:
                    
                    await asyncio.sleep(2)  
                else:
                    raise  
    except sa_exc.SQLAlchemyError as e:
        
        raise HTTPException(status_code=503, detail="Database is not responding after multiple attempts")


@app.post("/sales_looses")
async def start_sales_looses(input_data: CostomInput):
    validate = checking_dates_input(input_data, days_of_order=1)
    if isinstance(validate, JSONResponse):
        my_logger.error(f"Validation error date:{validate.body}")
        return JSONResponse(status_code=400, content={"detail": "Both start and finish dates are required."})
    
    my_logger.info("Validation passed sucessfully")
    date_start = validate.date_start
    date_finish = validate.date_finish
    try:
        result = sales_loose_analysis(start_date=date_start, end_date=date_finish)
    except Exception as e:
        my_logger.error(f"Error creating sales_loose_analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating sales_loose_analysis: {str(e)}")
    
    
    if isinstance(result, JSONResponse):
        my_logger.error(f"Validation error: {result.body}")
        raise HTTPException(status_code=result.status_code, detail=result.body.decode("utf-8"))
    
    

    try:
        test = create_xlsx_files_ziped(result)
        my_logger.info("ZIP archive with Excel file created successfully")
        return test
    except Exception as e:
        my_logger.error(f"Error creating ZIP archive: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating ZIP archive: {str(e)}")




@app.get("/groups")
async def groups_check():
    groups=create_groups_list()
    
    
    unique_groups_to_list = groups['group'].unique().tolist()


    return JSONResponse(status_code=200, content=unique_groups_to_list)

@app.get("/markets_list")
async def markets_list():
    markets = shop_name()
    unique_markets = markets['name'].unique().tolist()
    return JSONResponse(status_code=200, content=unique_markets)


@app.get("/prices_with_stocks")
async def prices():
    
    try:
        result = prices_with_stocks()
        if result.empty:
            return JSONResponse(status_code=404, content={"detail": "Немає даних за вчорашній день"})
       
        xlsx = create_xlsx_files_ziped(result, filenames="prices_with_stocks.xlsx")
        return xlsx
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Помилка: {str(e)}"}) 
    





@app.get("/redistribution/categories-hierarchy")
async def get_categories_hierarchy():
    """
    Retrieves the category hierarchy for frontend display.
    Returns hierarchy with group (level 0) as the filtering level.
    """
    my_logger.info("Fetching category hierarchy.")
    try:
        # Delegate to the helper function with target_level=0 (group = 1st level)
        hierarchy_output = get_category_hierarchy_tree(target_level=0)

        if not hierarchy_output:
            my_logger.warning("No hierarchy data returned.")
            return JSONResponse(status_code=200, content=[])

        my_logger.info("Successfully retrieved category hierarchy with group_id.")
        return JSONResponse(status_code=200, content=hierarchy_output)
    except Exception as e:
        my_logger.error(f"Error fetching category hierarchy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching category hierarchy: {str(e)}")

@app.get("/redistribution/shops-with-ids")
async def get_shops_with_ids():
    """
    Retrieves a list of all shops with their IDs and names.
    """
    my_logger.info("Fetching shops with IDs.")
    try:
        shops_df = shop_name() # existing function that returns shop ID and name
        all_warehouses_to_exclude = [warhause_id] + warhauses_smal
        shops_df = shops_df[~shops_df['id'].isin(all_warehouses_to_exclude)]
        shops_output = shops_df.to_dict(orient='records')
        my_logger.info("Successfully retrieved shops with IDs.")
        return JSONResponse(status_code=200, content=shops_output)
    except Exception as e:
        my_logger.error(f"Error fetching shops with IDs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching shops with IDs: {str(e)}")



@app.post("/auto_order_markets")
async def auto_order_markets(input_data: Costom_input_with_groups):
    my_logger.info(f"input_data: {input_data}")
    result = checking_dates_input(input_data, days_of_order=1)
    my_logger.debug(f"auto_order_markets result: {result} walues")
    if isinstance(result, JSONResponse):
        my_logger.error(f"Validation error date:{result.body}")
        return JSONResponse(status_code=400, content={"detail": "Both start and finish dates are required."})
    if result.groups:
        my_logger.debug(f"auto_order_markets groups:{result.groups}")
        try:
            clumns_for_managers, final_table_stage_2, db_status = auto_order_markets_start(result.date_start,result.date_finish,result.days_of_order,result.groups, result.markets, result.today_stocs_mode)
           
            if db_status['status'] == "error":
                    return JSONResponse(status_code=500, content=db_status)
            
            xlsx = create_xlsx_files_ziped((clumns_for_managers, final_table_stage_2))
            return xlsx
        except Exception as e:
            # Обробка непередбачених помилок
            return JSONResponse(status_code=500, content={"detail": f"Неочікувана помилка при обробці замовлення: {str(e)}"})

    
    my_logger.debug("auto_order_markets groups is None")
    return  JSONResponse(status_code=400, content={"detail": "Groups is None."})


@app.get("/market_down_products")
async def market_down_product_start():
    try:
        result = market_down_products_generate()
        my_logger.info(f"market_down_products_generate started")
    except Exception as e:
        my_logger.error(f"market_down_products_generate Error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error market_down_products_generate: {str(e)}")
    
    try:
        excel = create_xlsx_files_ziped(result, "Уцінка.xlsx")
        my_logger.info(f"xlsx creates sucesfully/market_down_products_generate ")
        return excel
    except Exception as e:
        my_logger.error(f"Error creating ZIP archive: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating ZIP archive: {str(e)}")


@app.post("/insurance_balance")
async def insurance_balance(input_data: CostomInput):
    validate = checking_dates_input(input_data, days_of_order=7)
    if isinstance(validate, JSONResponse):
        my_logger.error(f"Validation error date:{validate.body}")
        return JSONResponse(status_code=400, content={"detail": "Both start and finish dates are required."})
    my_logger.info("Validation passed sucessfully")
    date_start = validate.date_start
    date_finish = validate.date_finish
    try:
        result = insure_balance_builder(date_start=date_start, date_end=date_finish)
    except Exception as e:
        my_logger.error(f"Error creating ZIP archive: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error creating insure balance builder: {str(e)}")
    try:
        excel = create_xlsx_files_ziped(result)
        my_logger.info("xlsx created sucesfull")
        return excel
    except Exception as e:
        my_logger.error(f"Error creating ZIP archive: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating ZIP archive: {str(e)}")


@app.post("/archive_products")
async def start_archive_products(input_data: CostomInput):
    validate = checking_dates_input(input_data, days_of_order=1)
    if isinstance(validate, JSONResponse):
        my_logger.error(f"Validation error date:{validate.body}")
        return JSONResponse(status_code=400, content={"detail": "Both start and finish dates are required."})
    
    my_logger.info("Validation passed sucessfully")
    date_start = validate.date_start
    date_finish = validate.date_finish
    result = archive_products_analise(date_start, date_finish)
    if isinstance(result, JSONResponse):
        my_logger.error(f"Validation error: {result.body}")
        raise HTTPException(status_code=result.status_code, detail=result.body.decode("utf-8"))
    
    

    try:
        test = create_xlsx_files_ziped(result, "Archive_products.xlsx")
        my_logger.info("ZIP archive with Excel file created successfully")
        return test
    except Exception as e:
        my_logger.error(f"Error creating ZIP archive: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating ZIP archive: {str(e)}")





@app.post("/out_products")
async def start_out_products(input_data: CostomInput):
    validate = checking_dates_input(input_data, days_of_order=1)
    if isinstance(validate, JSONResponse):
        my_logger.error(f"Validation error date:{validate.body}")
        return JSONResponse(status_code=400, content={"detail": "Both start and finish dates are required."})
    
    my_logger.info("Validation passed sucessfully")
    date_start = validate.date_start
    date_finish = validate.date_finish
    result = analyze_out_products(date_start=date_start, date_finish=date_finish)
    if isinstance(result, JSONResponse):
        my_logger.error(f"Validation error: {result.body}")
        raise HTTPException(status_code=result.status_code, detail=result.body.decode("utf-8"))
    
    

    try:
        test = create_xlsx_files_ziped(result)
        my_logger.info("ZIP archive with Excel file created successfully")
        return test
    except Exception as e:
        my_logger.error(f"Error creating ZIP archive: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating ZIP archive: {str(e)}")





@app.post("/auto_order")
async def start_auto_order(input_data: AutoOrderInput):
    # Check if auto order process is already in progress
    my_logger.info("Received auto order request")
    if auto_order_lock.locked():
        return JSONResponse(status_code=409, content={"detail": "Auto order is already in progress."})

    date_start = input_data.date_start
    date_finish = input_data.date_finish
    days_of_order = input_data.days_of_order

    # Validate date_start
    if not date_start:
        return "No Start Date"
    elif (date_finish - date_start) < timedelta(days=7):
        return JSONResponse(status_code=400, content={"detail": "Days of order must be at least 7."})

    # Validate date_finish (considering both start and past requirement)
    if not date_start or not date_finish:
        return JSONResponse(status_code=400, content={"detail": "Both start and finish dates are required."})
    if date_finish >= date.today():
        return JSONResponse(status_code=400, content={"detail": "Finish date cannot be today or in the future."})
    if date_finish <= date_start:
        return JSONResponse(status_code=400, content={"detail": "Finish date must be after start date."})
    if days_of_order < 7:
        return JSONResponse(status_code=400, content={"detail": "Days of order must be at least 7."})
    




    # Use a lock to ensure only one auto order process runs at a time
    async with auto_order_lock:
        try:
            # Start timer for analysis
            start_time = time.time()
            
            # Call the auto_order_w_start function
            result_table, mid_table = await execute_auto_order_with_retries(input_data)
            my_logger.info(f"api - Auto_order_w start with {date_start}, {date_finish}, {days_of_order}")

            # Calculate analysis time and product count
            end_time = time.time()
            analysis_time = end_time - start_time
            product_count = len(result_table)

            # Якщо результат пустий, повертаємо JSON-помилку
            if result_table.empty:
                my_logger.error("No data available for the selected period.")
                return JSONResponse(status_code=404, content={"detail": "No data available for the selected period."})

            # Generate filename with current datetime
            current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_main = f"auto_order_w{current_datetime}.xlsx"

            #filename_mid = f"autoorder_test_{current_datetime}.xlsx"

            
            try:
                # Convert result to JSON format
                #json_result = table_to_json(result_table)
                #parsed_result = json.loads(json_result)

                #json_mid = table_to_json(mid_table)
                #parsed_mid_result = json.loads(json_mid)
                xlsx_file = io.BytesIO()
                with pd.ExcelWriter(xlsx_file, engine="openpyxl") as writer:
                    result_table.to_excel(writer, index=False)
                xlsx_file.seek(0)
                file_size = len(xlsx_file.getvalue())
                my_logger.debug(f"Generated XLSX file size: {file_size} bytes")

                return StreamingResponse(
                    xlsx_file,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={filename_main}",
                             "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             "Content-Length": str(file_size)
                             
                             }
                    )

        
            except Exception as xlsx_error:
                my_logger.exception("Error during XLSX file generation")
                return JSONResponse(status_code=500, content={"detail": f"Error generating XLSX file: {str(xlsx_error)}"})
        except sa_exc.SQLAlchemyError as e:
            # Якщо сталася помилка бази даних, наприклад, не вдалося з'єднатися
            my_logger.exception("Database error during auto order process")
            return JSONResponse(status_code=503, content={"detail": f"Database error: {str(e)}"})
        except Exception as e:
            # Загальна обробка інших помилок
            my_logger.exception("Error during auto order process")
            return JSONResponse(status_code=500, content={"detail": f"Unexpected error: {str(e)}"})


# --- New Endpoints for Redistribution ---

@app.post("/redistribution/generate-plan")
async def generate_redistribution_plan(input_data: RedistributionInput):
    """
    Generates a redistribution plan based on user input and returns an Excel file.
    """
    my_logger.info(f"Received request for redistribution plan generation.")
    
    try:
        redistribution_plan_df = redistribution_api_handler(
            date_start_str=input_data.date_start.isoformat(),
            date_finish_str=input_data.date_finish.isoformat(),
            days_of_analysis=input_data.days_of_analysis,
            min_surplus_coefficient=input_data.min_surplus_coefficient,
            donor_markets_ids=input_data.donor_markets_ids,
            recipient_markets_ids=input_data.recipient_markets_ids,
            selected_lowest_categories_names=input_data.selected_lowest_categories_names,
            today_stocs_mode=input_data.today_stocs_mode
        )

        if redistribution_plan_df.empty:
            my_logger.warning("No redistribution plan generated.")
            return JSONResponse(status_code=200, content={"message": "No redistribution plan generated based on the provided criteria."})

        # Format the DataFrame with Ukrainian column names and proper order
        formatted_df = format_redistribution_plan(redistribution_plan_df)
        
        # Use the existing create_xlsx_files_ziped function (same as autoorder_m)
        return create_xlsx_files_ziped(formatted_df, filenames=["Redistribution_Plan.xlsx"])
    except HTTPException as e:
        my_logger.error(f"Redistribution plan generation failed with HTTPException: {e.detail}")
        raise e
    except Exception as e:
        my_logger.error(f"Error during redistribution plan generation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate redistribution plan: {str(e)}")

#Test block

#test.to_csv("test_insure_balance.csv", index=False)
#x , y , z = sdp(date(2024,11,1), date(2024,11,16), detailed=True)
#test = Insure_Balance(x)
#z.to_excel("test_insure_balance.xlsx")
 #Test block       


if __name__ == "__main__":
    # Configure Hypercorn
    config = Config()
    config.bind = ["0.0.0.0:8000"]
    
    # Run the FastAPI app using Hypercorn
    asyncio.run(serve(app, config))

# To run with multiple workers:
# hypercorn main:app --workers 2
