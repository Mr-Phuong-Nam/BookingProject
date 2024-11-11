import pandas as pd
import re
from datetime import datetime, timedelta
from airflow.providers.postgres.hooks.postgres import PostgresHook

# Các hàm phụ trợ
# ----------------------------------------------------------------------------------------

def identify_pet_friendly(value):
    return False if value is None or 'not allowed' in value.lower() else True

def is_credit_card_required(list_value):
    return False if list_value is None or 'Cash' in list_value else True

def is_smoking_allowed(list_value):
    return False if list_value is None or 'Non-smoking rooms' in list_value else True

def extract_checkin_checkout_times(time_string):
    # Case: Availabel 24 hours
    if 'Available 24 hours' in time_string:
        return ('00:00', '23:59')  # Checkin: 00:00 và Checkout: 23:59
    time_string = time_string.strip().lower()

    if 'from' in time_string and 'to' in time_string:
        # Case: "From XX:00 to XX:00"
        parts = time_string.replace('from', '').replace('to', '').split()
        checkin_start = parts[0].strip()
        checkin_end = parts[1].strip()
        return (checkin_start, checkin_end)

    elif 'until' in time_string:
        # Case: "Until XX:00" (Only checkout_end is specified)
        checkout_end = time_string.replace('until', '').strip()
        return (None, checkout_end)

    return (None, None)

def clean_bed_str(value):
    return int(re.search(r'\d+', str(value)).group(0)) if value is not None else 0

# def clean_discount_column(value):
#     return float(re.search(r'\d+(\.\d+)?', str(value)).group(0)) if value is not None else 0.0
def clean_discount_column(value):
    if value is not None:
        match = re.search(r'\d+(\.\d+)?', str(value))
        if match:
            return float(match.group(0))
        else:
            return 0.0
    else:
        return 0.0
# --------------------------------------------------------------------------------------------------------------------------------------

# -----------------------------------------------------------------------------------------------------------------------------
# Hàm xử lý bảng Accommodation
def AccommodationProcess(**kwargs):
    ti = kwargs['ti']
    json_data = ti.xcom_pull(task_ids='push_json_acc_to_xcom', key='scrapy_json_data')
    print(f"DataFrame: {json_data}")

    data = pd.DataFrame(json_data)
    data = data.dropna(subset=['id'])
   
    accommodation_df = pd.DataFrame({
        'acm_id': data['id'].astype(int), 
        'acm_name': data['name'].astype(str),  
        'acm_type': data['typeId'].astype(str),  
        'acm_star_rating': data['star'].fillna(0).astype(int),
        'acm_amenities': data['unities'].astype(str), 
        'acm_description': data['description'].astype(str),  
        'acm_customer_rating': data['reviewScore'].astype(float),  
        'acm_review_count': data['reviewCount'].astype(int), 
        'acm_location': data['location'].astype(str),
        'acm_address': data['address'].astype(str),
        'acm_lat': data['lat'].astype(float).round(6),
        'acm_long': data['lng'].astype(float).round(6),
        'acm_url': data['url'].astype(str)
    })

    pg_hook = PostgresHook(postgre_conn_id='postgres_default')
    engine = pg_hook.get_sqlalchemy_engine()
    
    with engine.connect() as conn:
        for _, row in accommodation_df.iterrows():
            insert_stmt = """
                INSERT INTO "Accommodation" (acm_id, acm_name, acm_type, acm_star_rating, acm_amenities, 
                                           acm_description, acm_customer_rating, acm_review_count, acm_address, 
                                           acm_location, acm_lat, acm_long, acm_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (acm_id) DO UPDATE SET
                    acm_name = EXCLUDED.acm_name,
                    acm_type = EXCLUDED.acm_type,
                    acm_star_rating = EXCLUDED.acm_star_rating,
                    acm_amenities = EXCLUDED.acm_amenities,
                    acm_description = EXCLUDED.acm_description,
                    acm_customer_rating = EXCLUDED.acm_customer_rating,
                    acm_review_count = EXCLUDED.acm_review_count,
                    acm_address = EXCLUDED.acm_address,
                    acm_location = EXCLUDED.acm_location,
                    acm_lat = EXCLUDED.acm_lat,
                    acm_long = EXCLUDED.acm_long,
                    acm_url = EXCLUDED.acm_url;
            """
            conn.execute(insert_stmt, (
                row['acm_id'], row['acm_name'], row['acm_type'], row['acm_star_rating'], row['acm_amenities'],
                row['acm_description'], row['acm_customer_rating'], row['acm_review_count'], row['acm_address'],
                row['acm_location'], row['acm_lat'], row['acm_long'], row['acm_url'] 
            ))

    print("Data loaded successfully to Accommodation table.")

# Hàm xử lý bảng Disciplines
def DisciplinesProcess(**kwargs):
    ti = kwargs['ti']
    json_data = ti.xcom_pull(task_ids='push_json_acc_to_xcom', key='scrapy_json_data')
    print(f"DataFrame: {json_data}")

    data = pd.DataFrame(json_data)
    data = data.dropna(subset=['id'])

    disciplines_df = pd.DataFrame({
        'dis_accommodation_id': data['id'].astype(int),
        'dis_is_pet_allowed': data['petInfo'].apply(identify_pet_friendly).astype(bool),
        'dis_credit_card_required': data['paymentMethods'].apply(is_credit_card_required).astype(bool),

        'dis_payment_methods': data['paymentMethods'].astype(str),
        'dis_smoking_allowed': data['unities'].apply(is_smoking_allowed).astype(bool),
        'dis_checkin_start': data['checkinTime'].apply(lambda x: extract_checkin_checkout_times(str(x))[0]),
        'dis_checkin_end': data['checkinTime'].apply(lambda x: extract_checkin_checkout_times(str(x))[1]),
        'dis_checkout_start': data['checkoutTime'].apply(lambda x: extract_checkin_checkout_times(str(x))[0]),
        'dis_checkout_end': data['checkoutTime'].apply(lambda x: extract_checkin_checkout_times(str(x))[1])
    }) 

    pg_hook = PostgresHook(postgre_conn_id='postgres_default')
    engine = pg_hook.get_sqlalchemy_engine()
    
    with engine.connect() as conn:
        for _, row in disciplines_df.iterrows():
            insert_stmt = """
                INSERT INTO "Disciplines" (dis_accommodation_id, dis_is_pet_allowed, dis_credit_card_required, 
                                         dis_payment_methods, dis_smoking_allowed, dis_checkin_start, 
                                         dis_checkin_end, dis_checkout_start, dis_checkout_end)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dis_accommodation_id) DO UPDATE SET
                    dis_is_pet_allowed = EXCLUDED.dis_is_pet_allowed,
                    dis_credit_card_required = EXCLUDED.dis_credit_card_required,
                    dis_payment_methods = EXCLUDED.dis_payment_methods,
                    dis_smoking_allowed = EXCLUDED.dis_smoking_allowed,
                    dis_checkin_start = EXCLUDED.dis_checkin_start,
                    dis_checkin_end = EXCLUDED.dis_checkin_end,
                    dis_checkout_start = EXCLUDED.dis_checkout_start,
                    dis_checkout_end = EXCLUDED.dis_checkout_end;
            """
            conn.execute(insert_stmt, tuple(row))

    print("Data loaded successfully to Disciplines table.")

# Hàm xử lý theo bảng Room
def RoomProcess(**kwargs):
    ti = kwargs['ti']
    json_data = ti.xcom_pull(task_ids='push_json_price_to_xcom', key='scrapy_json_data')
    print(f"DataFrame: {json_data}")

    data = pd.DataFrame(json_data)
    data = data.dropna(subset=['roomId', 'accommodationId'])  

    room_df = pd.DataFrame({
        'rm_room_id': data['roomId'].astype(int),               
        'rm_accommodation_id': data['accommodationId'].astype(int),      
        'rm_name': data['roomName'].astype(str),                
        'rm_guests_number': data['numGuests'].apply(clean_bed_str).astype(int),
        'rm_area': data['roomArea'].apply(clean_bed_str).astype(float),
        'rm_bed_types': data['beds'].astype(str)
    })
    
    pg_hook = PostgresHook(postgre_conn_id='postgres_default')
    engine = pg_hook.get_sqlalchemy_engine()
    
    with engine.connect() as conn:
        for _, row in room_df.iterrows():
            insert_stmt = """
                INSERT INTO "Rooms" (rm_room_id, rm_accommodation_id, rm_name, rm_guests_number, rm_area, rm_bed_types)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (rm_room_id, rm_accommodation_id) DO UPDATE SET
                    rm_name = EXCLUDED.rm_name,
                    rm_guests_number = EXCLUDED.rm_guests_number,
                    rm_area = EXCLUDED.rm_area,
                    rm_bed_types = EXCLUDED.rm_bed_types;
            """
            conn.execute(insert_stmt, tuple(row))

    print("Data loaded successfully to Rooms table.")

# Hàm xử lý theo bảng Bed_price
def BedPriceProcess(**kwargs):
    ti = kwargs['ti']
    json_data = ti.xcom_pull(task_ids='push_json_price_to_xcom', key='scrapy_json_data')
    print(f"DataFrame: {json_data}")

    data = pd.DataFrame(json_data)
    data = data.dropna(subset=['roomId', 'accommodationId'])

    data['checkin'] = pd.to_datetime(data['checkin'], format='%Y-%m-%d', errors='coerce').dt.date
    data['checkout'] = pd.to_datetime(data['checkout'], format='%Y-%m-%d', errors='coerce').dt.date

    crawled_date = datetime.today().date()
    crawled_date += timedelta(hours=7)

    bed_price_df = pd.DataFrame({
        'bp_crawled_date': crawled_date,
        'bp_future_interval': (data['checkin'] - crawled_date).apply(lambda x: x.days).astype(int),
        'bp_room_id': data['roomId'].astype(int),
        'bp_accommodation_id': data['accommodationId'].astype(int),
        'bp_price': data['price'].astype(int),
        'bp_current_discount': data['discount'].apply(clean_discount_column).astype(float),
    })
    
    pg_hook = PostgresHook(postgre_conn_id='postgres_default')
    engine = pg_hook.get_sqlalchemy_engine()
    
    bed_price_df.to_sql('Bed_price', engine, if_exists='append', index=False)
    print("Data loaded successfully to Bed_price table.")