from datetime import date, time, timedelta, datetime 
def store_day():
    today = date.today()
    
    current_time_obj = datetime.now().time() 
    
    start_time = time(8, 0, 1) 
    end_time = time(23, 59, 59) 

   
    if start_time <= current_time_obj <= end_time:
        store_day_result = today + timedelta(days=1)
    else:
        store_day_result = today 
    
    return store_day_result

x = store_day()
print(x)