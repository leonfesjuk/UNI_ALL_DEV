
from api.helpers.loger import init_logger
import io
import zipfile
from datetime import datetime
import pandas as pd
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import sqlalchemy.exc as sa_exc

my_logger = init_logger()
my_logger.debug("Логер ініціалізований у xlsx_maker.py")

import io
import zipfile
from datetime import datetime
import pandas as pd
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
import sqlalchemy.exc as sa_exc

def create_xlsx_files_ziped(dataframes, filenames=None):
    
    """
    Generate XLSX-files for one or more DataFrames and return them as a ZIP archive.

    :param dataframes: List of pandas.DataFrame or a single DataFrame.
    :param filenames: List of file names (optional). If None, names are generated automatically.
    :return: StreamingResponse containing a ZIP archive.
    """
    try:
        # if put 1 DataFrame into list
        if isinstance(dataframes, pd.DataFrame):
            dataframes = [dataframes]
            my_logger.debug(
                f"Функція create_xlsx_files викликана: dataframes={len(dataframes)}, "
                f"filenames={len(filenames) if filenames is not None else 'None'}")
        # generate filenames if not provided
        if filenames is None:
            filenames = []
            current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
            for i, df in enumerate(dataframes):
                filenames.append(f"file{current_datetime}_{i + 1}.xlsx")
        elif isinstance(filenames, str):
            # If 1 name is provided, put it into list
            filenames = [filenames]
        
        # check if number of DataFrames matches number of filenames
        if len(dataframes) != len(filenames):
            my_logger.error("Кількість DataFrame повинна відповідати кількості імен файлів.")
            raise ValueError("Кількість DataFrame повинна відповідати кількості імен файлів.")
        
        # Create zip-archive
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for df, filename in zip(dataframes, filenames):
                xlsx_file = io.BytesIO()
                
                with pd.ExcelWriter(xlsx_file, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False)
                
                xlsx_file.seek(0)
                zip_file.writestr(filename, xlsx_file.getvalue())
        
        zip_buffer.seek(0)
        my_logger.info("xlsx_file generated and zipped")
        
        # Put the zip-archive into a response and return it
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=auto_orders.zip",
                "Content-Type": "application/zip"
            }
        )
    
    
    except Exception as xlsx_error:
        my_logger.error(f"Error generating XLSX file: {str(xlsx_error)}")
        raise HTTPException(status_code=500, detail=f"Error generating XLSX file: {str(xlsx_error)}")

# Приклад використання
#dataframes = [df1, df2, df3]  # Список DataFrame
#response = create_xlsx_files(dataframes)