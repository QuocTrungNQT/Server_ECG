import string
from flask import Flask, request, jsonify
import time
import pandas as pd
import tensorflow as tf
import numpy as np
from keras.models import load_model
from flask_cors import CORS, cross_origin

# 1. Khởi tạo ứng dụng
app = Flask(__name__)
CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"

# 2. Khai báo các thông số
data_path = 'data/Test_ECG.csv'
model_path = 'model/New_Proposed_CNN_CNN_PastECG_FutureCls_1-mininput_5-minoutput.h5'
minute_input_arr = 1 #fix 15 min lun đừng đổi chỗ này
minute_input = 1
minute_output = 5
window_input_arr = 40 * minute_input_arr
window_input = 40 * minute_input
window_out = 40 * minute_output
length_ecg = 187 
batch_size = 16
# Biến toàn cục để lưu trạng thái đọc dữ liệu
global_chunk_position = 800

# 3. Đọc file csv
class CombinedDataset:
    def __init__(self, X, X_arr, y):
        self.X = X
        self.X_arr = X_arr
        self.y = y

    def __getitem__(self, index):
        X_window = self.X[index]
        X_window_arr = self.X_arr[index]
        y_value = self.y[index]
        return X_window, X_window_arr, y_value

    def __len__(self):
        return len(self.X)
    
class CombinedDataLoader(tf.keras.utils.Sequence):
    def __init__(self, dataset, batch_size, size):
        self.dataset = dataset
        self.batch_size = batch_size
        self.size = size
        self.num_batches = size // batch_size

    def __getitem__(self, i):
        if i < self.num_batches:
            start = i * self.batch_size
            stop = (i + 1) * self.batch_size

            data = [self.dataset[j] for j in range(start, stop)]

            X1_batch = np.stack([sample[0] for sample in data], axis=0)
            X2_batch = np.stack([sample[1] for sample in data], axis=0)
            y_batch = np.array([sample[2] for sample in data])
            return [X1_batch, X2_batch], y_batch
        else:
            # Xử lý batch cuối cùng riêng biệt
            remaining_samples = self.size - (self.num_batches * self.batch_size)
            data = [self.dataset[j] for j in range(self.num_batches * self.batch_size, self.size)]

            X1_batch = np.stack([sample[0] for sample in data], axis=0)
            X2_batch = np.stack([sample[1] for sample in data], axis=0)
            y_batch = np.array([sample[2] for sample in data])

            return [X1_batch, X2_batch], y_batch

    def __len__(self):
        return self.num_batches + 1

# 4. Định nghĩa API
@app.route('/')
def home():
    return 'home'

@app.route('/predict', methods=['GET'])
def predict():
    try:
        global global_chunk_position
        chunk_size = 40

        # Đọc chunk hiện tại từ vị trí lưu trữ
        chunk_iterator = pd.read_csv(data_path, chunksize=chunk_size, header=None, skiprows=global_chunk_position)

        try:
            chunk = next(chunk_iterator)
            global_chunk_position += chunk_size  # Cập nhật vị trí đọc tiếp theo
        except StopIteration:
            return jsonify({'message': 'datainput invalid'})

        # Kiểm tra kích thước chunk
        if len(chunk) < chunk_size:
            return jsonify({'message': 'datainput invalid'})

        # Xử lý chunk
        df = chunk
        data = df.drop(columns=length_ecg)  # ECG
        data = data.values
        data1 = df.iloc[:, length_ecg]  # ARR

        X_window_arr = np.array(data1[:window_input_arr]).reshape(window_input_arr, 1)
        X_window = data[:window_input_arr]
        y_value = data1[:window_input_arr]

        X_arr = [X_window_arr]
        X = [X_window]
        y = [y_value]

        # Tạo dataset và dataloader
        combined_test_dataset = CombinedDataset(X, X_arr, y)
        combined_test_loader = CombinedDataLoader(combined_test_dataset, batch_size, len(combined_test_dataset))

        # Tải mô hình và dự đoán kết quả
        model = load_model(model_path)
        predictions = model.predict(combined_test_loader)
        y_pred = np.argmax(predictions, axis=1)

        predicted_label = (y_pred[0])

        if predicted_label ==0:
            classification = 'Normal'
        else:
            classification = 'Abnormal'
        # return jsonify(predictions=predicted_label)

        # # Trả về dự đoán dưới dạng JSON
        result = {'predictions': classification,
                  'ECG':data[39].tolist()}
        return jsonify(result)

    except Exception as e:
        error_message = str(e)
        return jsonify({'error': error_message}), 500

if __name__ == '__main__':

    app.run(debug=True)