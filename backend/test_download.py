import kagglehub

# Download latest version
path = kagglehub.dataset_download("surajjha101/bigbasket-entire-product-list-28k-datapoints")

print("Path to dataset files:", path)