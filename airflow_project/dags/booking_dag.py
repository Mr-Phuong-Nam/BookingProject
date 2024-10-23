
from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.bash import BashOperator
import pandas as pd
from airflow.operators.python import PythonOperator
import pandas as pd
import numpy as np
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime
import json
from airflow.utils.decorators import apply_defaults
from airflow.models import BaseOperator
from processData import *

CURRENT_DATE = datetime.now().strftime("%Y-%m-%d")

# Define the default arguments
default_args = {
    'owner': 'cheep',
    'email': ['21120576@student.hcmus.edu.vn'],
    'email_on_failure': True,
    'email_on_retry': False,
    'depends_on_past': False,
    'start_date': days_ago(0),  # Set start_date to the current date and time
}


class PushJsonToXComOperator(BaseOperator):
    @apply_defaults
    def __init__(self, file_path, xcom_key, *args, **kwargs):
        super(PushJsonToXComOperator, self).__init__(*args, **kwargs)
        self.file_path = file_path
        self.xcom_key = xcom_key

    def execute(self, context):
        # Read the JSON data from the file
        with open(self.file_path, 'r', encoding='utf-8') as file:
            json_data = json.load(file)

        # Push the JSON data to XCom
        self.xcom_push(context, key=self.xcom_key, value=json_data)




# Define the DAG
with DAG(
    dag_id='booking_scraping_dag',
    default_args=default_args,
    schedule_interval='0 8 * * *',
    catchup=False,
) as dag:

    # define the first task
    task1 = BashOperator(
        task_id='run_booking_scrapy',
        # cd /Users/mac/HCMUS/ItelligentAnalApp/python_scripts/airflow_temp/booking && scrapy crawl booking
        bash_command='cd /opt/airflow/booking && scrapy crawl accommodation',
        dag=dag,
    )

    task2 = BashOperator(
        task_id='run_price_scrapy',
        # cd /Users/mac/HCMUS/ItelligentAnalApp/python_scripts/airflow_temp/booking && scrapy crawl booking
        bash_command='cd /opt/airflow/booking && scrapy crawl price',
        dag=dag,
    )

    # Define the task to push JSON data to XCom
    push_json_acc_task = PushJsonToXComOperator(

        task_id='push_json_acc_to_xcom',
        file_path=f'/opt/airflow/booking/hotel_data/{CURRENT_DATE}-AccommodationItem.json',  # Adjust the file path as needed
        xcom_key='scrapy_json_data',
        dag=dag,
    )

    push_json_price_task = PushJsonToXComOperator(
            
        task_id='push_json_price_to_xcom',
        file_path=f'/opt/airflow/booking/hotel_data/{CURRENT_DATE}-RoomPriceItem.json',  # Adjust the file path as needed
        xcom_key='scrapy_json_data',
        dag=dag,
    )

    process_accommodation_task = PythonOperator(
        task_id='process_accommodation_data',
        python_callable=AccommodationProcess,
        provide_context=True,  
        op_kwargs={'execution_date': '{{ ds }}'} 
    )

    process_descriplines_task = PythonOperator(
        task_id='process_descriplines_data',
        python_callable=DescriplinesProcess,
        provide_context=True,  
        op_kwargs={'execution_date': '{{ ds }}'} 
    )

    process_room_task = PythonOperator(
        task_id='process_room_data',
        python_callable=RoomProcess,
        provide_context=True,  
        op_kwargs={'execution_date': '{{ ds }}'} 
    )

    process_bed_price_task = PythonOperator(
        task_id='process_be_price_data',
        python_callable=BedPriceProcess,
        provide_context=True,  
        op_kwargs={'execution_date': '{{ ds }}'} 
    )



    # task5
    # task pipeline
    task1 >> push_json_acc_task >> [process_accommodation_task, process_descriplines_task]
    task1 >> task2 >> push_json_price_task >> [process_room_task, process_bed_price_task]
