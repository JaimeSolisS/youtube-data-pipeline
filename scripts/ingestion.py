import sys
import boto3

s3 = boto3.client("s3")

regions = ["CA", "DE", "FR", "GB", "IN", "JP", "KR", "MX", "RU", "US"]

bucket = sys.argv[1]
main_folder = "youtube"
csv_folder = "raw_statistics"
json_folder = "raw_statistics_reference_data"


print('starting upload...')
for region in regions: 
    print(f'{region} region:')
    lower_region = region.lower()
    
    csv_file = f'../data/{region}videos.csv'
    csv_s3_key = f'{main_folder}/{csv_folder}/region={lower_region}/{region}videos.csv'
    s3.upload_file(csv_file, bucket, csv_s3_key)
    print(f"csv uploaded {csv_file} to s3://{bucket}/{csv_s3_key}")
    
    json_file = f'../data/{region}_category_id.json'
    json_s3_key = f'{main_folder}/{json_folder}/region={lower_region}/{region}_category_id.json'
    s3.upload_file(json_file, bucket, json_s3_key)
    print(f"json uploaded {json_file} to s3://{bucket}/{json_s3_key}")
    
print("all files uploaded!")