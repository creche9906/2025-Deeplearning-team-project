
pip install keras-tcn

#PM10
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.svm import SVR
from sklearn.metrics import r2_score
from scipy.stats import ttest_rel
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '1'
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Conv1D, MaxPooling1D, Flatten
from tcn import TCN

# --- 1. 데이터 준비 ---
try:
    df10 = pd.read_csv('pm10.csv')
except FileNotFoundError:
    print("pm10.csv 파일을 찾을 수 없습니다. 스크립트와 동일한 디렉토리에 있는지 확인하세요.")
    exit()

# 모델 학습에 사용할 특성(feature)들을 정의
features = ['PM2.5', '오 존', '이산화질소', '일산화탄소', '아황산가스',
            '평균기온(°C)', '평균 풍속(m/s)', '평균 상대습도(%)', '평균 현지기압(hPa)', 'PM10_MA7', 'PM10_MA30', 'PM10lag',
            'Autumn', 'Spring', 'Summer', 'Winter']

X, y = [], []
for i in range(7, len(df10)):
    X.append(df10.loc[i-7:i-1, features].values)
    y.append(df10.loc[i, 'PM10'])

X = np.array(X)
y = np.array(y)

# --- 2. 10-겹 교차 검증 및 모델 평가 ---
# 데이터를 10개의 폴드(fold)로 나누어 교차 검증을 수행
kf = KFold(n_splits=10, shuffle=True, random_state=42)

# 각 모델(SVR, LSTM, CNN, TCN)의 폴드별 R2 점수를 저장할 리스트를 초기화합니다.
svr_scores, lstm_scores, cnn_scores, tcn_scores = [], [], [], []

print("10-겹 교차 검증을 시작합니다...")
# 10-겹 교차 검증 루프를 실행합니다.
for i, (train_index, test_index) in enumerate(kf.split(X)):
    print(f"--- 폴드 {i+1}/10 ---")
    X_train, X_test = X[train_index], X[test_index]
    y_train, y_test = y[train_index], y[test_index]

    # --- a) SVR 모델 (베이스라인) ---
    X_train_svr = X_train.reshape(X_train.shape[0], -1)
    X_test_svr = X_test.reshape(X_test.shape[0], -1)

    svr_model = SVR()
    svr_model.fit(X_train_svr, y_train)
    y_pred_svr = svr_model.predict(X_test_svr)
    svr_scores.append(r2_score(y_test, y_pred_svr))
    print(f"SVR 폴드 {i+1} R2: {svr_scores[-1]:.3f}")

    # --- b) LSTM 모델 ---
    lstm_model = Sequential([
        LSTM(64, activation='tanh', input_shape=(X_train.shape[1], X_train.shape[2])),
        Dense(1)
    ])
    lstm_model.compile(optimizer='adam', loss='mse')
    lstm_model.fit(X_train, y_train, epochs=50, batch_size=32, verbose=0)
    y_pred_lstm = lstm_model.predict(X_test, verbose=0).flatten()
    lstm_scores.append(r2_score(y_test, y_pred_lstm))
    print(f"LSTM 폴드 {i+1} R2: {lstm_scores[-1]:.3f}")

    # --- c) 1D-CNN 모델 ---
    cnn_model = Sequential([
        Conv1D(filters=64, kernel_size=3, activation='relu', input_shape=(X_train.shape[1], X_train.shape[2])),
        MaxPooling1D(pool_size=2),
        Flatten(),
        Dense(32, activation='relu'),
        Dense(1)
    ])
    cnn_model.compile(optimizer='adam', loss='mse')
    cnn_model.fit(X_train, y_train, epochs=50, batch_size=32, verbose=0)
    y_pred_cnn = cnn_model.predict(X_test, verbose=0).flatten()
    cnn_scores.append(r2_score(y_test, y_pred_cnn))
    print(f"1D-CNN 폴드 {i+1} R2: {cnn_scores[-1]:.3f}")

    # --- d) TCN 모델 ---
    tcn_model = Sequential([
        TCN(input_shape=(X_train.shape[1], X_train.shape[2]),
            nb_filters=64,
            kernel_size=3,
            dilations=[1, 2, 4],
            return_sequences=False),
        Dense(1)
    ])
    tcn_model.compile(optimizer='adam', loss='mse')
    tcn_model.fit(X_train, y_train, epochs=50, batch_size=32, verbose=0)
    y_pred_tcn = tcn_model.predict(X_test, verbose=0).flatten()
    tcn_scores.append(r2_score(y_test, y_pred_tcn))
    print(f"TCN 폴드 {i+1} R2: {tcn_scores[-1]:.3f}")

print("\n교차 검증이 완료되었습니다.\n")

# --- 3. 성능 요약 및 통계적 검정 ---
print("--- PM10 예측 모델 성능 비교 ---")
# 각 모델의 폴드별 R2 점수를 소수점 셋째 자리까지 반올림하여 출력
print(f"SVR (A)    R2 점수: {np.round(svr_scores, 3)}")
print(f"LSTM (B)   R2 점수: {np.round(lstm_scores, 3)}")
print(f"1D-CNN (C) R2 점수: {np.round(cnn_scores, 3)}")
print(f"TCN (D)    R2 점수: {np.round(tcn_scores, 3)}\n")

# 각 모델의 평균 R2 점수를 출력
print(f"SVR (A)    평균 R2: {np.mean(svr_scores):.3f}")
print(f"LSTM (B)   평균 R2: {np.mean(lstm_scores):.3f}")
print(f"1D-CNN (C) 평균 R2: {np.mean(cnn_scores):.3f}")
print(f"TCN (D)    평균 R2: {np.mean(tcn_scores):.3f}\n")

print("--- SVR 베이스라인(A) 대비 대응표본 T-검정 ---")
# 각 딥러닝 모델과 SVR 모델 간의 R2 점수 분포에 통계적으로 유의미한 차이가 있는지 확인
t_stat_lstm, p_val_lstm = ttest_rel(lstm_scores, svr_scores)
t_stat_cnn, p_val_cnn = ttest_rel(cnn_scores, svr_scores)
t_stat_tcn, p_val_tcn = ttest_rel(tcn_scores, svr_scores)

print("비교: LSTM (B) vs SVR (A)")
print(f"T-통계량: {t_stat_lstm:.4f}, P-값: {p_val_lstm:.4f}\n")

print("비교: 1D-CNN (C) vs SVR (A)")
print(f"T-통계량: {t_stat_cnn:.4f}, P-값: {p_val_cnn:.4f}\n")

print("비교: TCN (D) vs SVR (A)")
print(f"T-통계량: {t_stat_tcn:.4f}, P-값: {p_val_tcn:.4f}\n")


print("--- 딥러닝 모델 간 대응표본 T-검정 ---")
# 딥러닝 모델들 간의 성능 차이가 통계적으로 유의미한지 확인
t_stat_lstm_cnn, p_val_lstm_cnn = ttest_rel(lstm_scores, cnn_scores)
t_stat_lstm_tcn, p_val_lstm_tcn = ttest_rel(lstm_scores, tcn_scores)
t_stat_cnn_tcn, p_val_cnn_tcn = ttest_rel(cnn_scores, tcn_scores)

print("비교: LSTM (B) vs 1D-CNN (C)")
print(f"T-통계량: {t_stat_lstm_cnn:.4f}, P-값: {p_val_lstm_cnn:.4f}\n")

print("비교: LSTM (B) vs TCN (D)")
print(f"T-통계량: {t_stat_lstm_tcn:.4f}, P-값: {p_val_lstm_tcn:.4f}\n")

print("비교: 1D-CNN (C) vs TCN (D)")
print(f"T-통계량: {t_stat_cnn_tcn:.4f}, P-값: {p_val_cnn_tcn:.4f}")

#PM2.5
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.svm import SVR
from sklearn.metrics import r2_score
from scipy.stats import ttest_rel
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '1'
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Conv1D, MaxPooling1D, Flatten
from tcn import TCN

# --- 1. 데이터 준비 ---
try:
    df2 = pd.read_csv('pm25.csv')
except FileNotFoundError:
    print("pm25.csv 파일을 찾을 수 없습니다. 스크립트와 동일한 디렉토리에 있는지 확인하세요.")
    exit()

# 모델 학습에 사용할 특성(feature)들을 정의
features = ['PM10', '오 존', '이산화질소', '일산화탄소', '아황산가스',
            '평균기온(°C)', '평균 풍속(m/s)', '평균 상대습도(%)', '평균 현지기압(hPa)', 'PM2.5_MA7', 'PM2.5_MA30', 'PM2.5lag',
            'Autumn', 'Spring', 'Summer', 'Winter']

X, y = [], []
for i in range(7, len(df2)):
    X.append(df2.loc[i-7:i-1, features].values)
    y.append(df2.loc[i, 'PM2.5'])

X = np.array(X)
y = np.array(y)

# --- 2. 10-겹 교차 검증 및 모델 평가 ---
# 데이터를 10개의 폴드(fold)로 나누어 교차 검증을 수행
kf = KFold(n_splits=10, shuffle=True, random_state=42)

# 각 모델(SVR, LSTM, CNN, TCN)의 폴드별 R2 점수를 저장할 리스트를 초기화합니다.
svr_scores, lstm_scores, cnn_scores, tcn_scores = [], [], [], []

print("10-겹 교차 검증을 시작합니다...")
# 10-겹 교차 검증 루프를 실행합니다.
for i, (train_index, test_index) in enumerate(kf.split(X)):
    print(f"--- 폴드 {i+1}/10 ---")
    X_train, X_test = X[train_index], X[test_index]
    y_train, y_test = y[train_index], y[test_index]

    # --- a) SVR 모델 (베이스라인) ---
    X_train_svr = X_train.reshape(X_train.shape[0], -1)
    X_test_svr = X_test.reshape(X_test.shape[0], -1)

    svr_model = SVR()
    svr_model.fit(X_train_svr, y_train)
    y_pred_svr = svr_model.predict(X_test_svr)
    svr_scores.append(r2_score(y_test, y_pred_svr))
    print(f"SVR 폴드 {i+1} R2: {svr_scores[-1]:.3f}")

    # --- b) LSTM 모델 ---
    lstm_model = Sequential([
        LSTM(64, activation='tanh', input_shape=(X_train.shape[1], X_train.shape[2])),
        Dense(1)
    ])
    lstm_model.compile(optimizer='adam', loss='mse')
    lstm_model.fit(X_train, y_train, epochs=50, batch_size=32, verbose=0)
    y_pred_lstm = lstm_model.predict(X_test, verbose=0).flatten()
    lstm_scores.append(r2_score(y_test, y_pred_lstm))
    print(f"LSTM 폴드 {i+1} R2: {lstm_scores[-1]:.3f}")

    # --- c) 1D-CNN 모델 ---
    cnn_model = Sequential([
        Conv1D(filters=64, kernel_size=3, activation='relu', input_shape=(X_train.shape[1], X_train.shape[2])),
        MaxPooling1D(pool_size=2),
        Flatten(),
        Dense(32, activation='relu'),
        Dense(1)
    ])
    cnn_model.compile(optimizer='adam', loss='mse')
    cnn_model.fit(X_train, y_train, epochs=50, batch_size=32, verbose=0)
    y_pred_cnn = cnn_model.predict(X_test, verbose=0).flatten()
    cnn_scores.append(r2_score(y_test, y_pred_cnn))
    print(f"1D-CNN 폴드 {i+1} R2: {cnn_scores[-1]:.3f}")

    # --- d) TCN 모델 ---
    tcn_model = Sequential([
        TCN(input_shape=(X_train.shape[1], X_train.shape[2]),
            nb_filters=64,
            kernel_size=3,
            dilations=[1, 2, 4],
            return_sequences=False),
        Dense(1)
    ])
    tcn_model.compile(optimizer='adam', loss='mse')
    tcn_model.fit(X_train, y_train, epochs=50, batch_size=32, verbose=0)
    y_pred_tcn = tcn_model.predict(X_test, verbose=0).flatten()
    tcn_scores.append(r2_score(y_test, y_pred_tcn))
    print(f"TCN 폴드 {i+1} R2: {tcn_scores[-1]:.3f}")

print("\n교차 검증이 완료되었습니다.\n")

# --- 3. 성능 요약 및 통계적 검정 ---
print("--- PM10 예측 모델 성능 비교 ---")
# 각 모델의 폴드별 R2 점수를 소수점 셋째 자리까지 반올림하여 출력
print(f"SVR (A)    R2 점수: {np.round(svr_scores, 3)}")
print(f"LSTM (B)   R2 점수: {np.round(lstm_scores, 3)}")
print(f"1D-CNN (C) R2 점수: {np.round(cnn_scores, 3)}")
print(f"TCN (D)    R2 점수: {np.round(tcn_scores, 3)}\n")

# 각 모델의 평균 R2 점수를 출력
print(f"SVR (A)    평균 R2: {np.mean(svr_scores):.3f}")
print(f"LSTM (B)   평균 R2: {np.mean(lstm_scores):.3f}")
print(f"1D-CNN (C) 평균 R2: {np.mean(cnn_scores):.3f}")
print(f"TCN (D)    평균 R2: {np.mean(tcn_scores):.3f}\n")

print("--- SVR 베이스라인(A) 대비 대응표본 T-검정 ---")
# 각 딥러닝 모델과 SVR 모델 간의 R2 점수 분포에 통계적으로 유의미한 차이가 있는지 확인
t_stat_lstm, p_val_lstm = ttest_rel(lstm_scores, svr_scores)
t_stat_cnn, p_val_cnn = ttest_rel(cnn_scores, svr_scores)
t_stat_tcn, p_val_tcn = ttest_rel(tcn_scores, svr_scores)

print("비교: LSTM (B) vs SVR (A)")
print(f"T-통계량: {t_stat_lstm:.4f}, P-값: {p_val_lstm:.4f}\n")

print("비교: 1D-CNN (C) vs SVR (A)")
print(f"T-통계량: {t_stat_cnn:.4f}, P-값: {p_val_cnn:.4f}\n")

print("비교: TCN (D) vs SVR (A)")
print(f"T-통계량: {t_stat_tcn:.4f}, P-값: {p_val_tcn:.4f}\n")


print("--- 딥러닝 모델 간 대응표본 T-검정 ---")
# 딥러닝 모델들 간의 성능 차이가 통계적으로 유의미한지 확인
t_stat_lstm_cnn, p_val_lstm_cnn = ttest_rel(lstm_scores, cnn_scores)
t_stat_lstm_tcn, p_val_lstm_tcn = ttest_rel(lstm_scores, tcn_scores)
t_stat_cnn_tcn, p_val_cnn_tcn = ttest_rel(cnn_scores, tcn_scores)

print("비교: LSTM (B) vs 1D-CNN (C)")
print(f"T-통계량: {t_stat_lstm_cnn:.4f}, P-값: {p_val_lstm_cnn:.4f}\n")

print("비교: LSTM (B) vs TCN (D)")
print(f"T-통계량: {t_stat_lstm_tcn:.4f}, P-값: {p_val_lstm_tcn:.4f}\n")

print("비교: 1D-CNN (C) vs TCN (D)")
print(f"T-통계량: {t_stat_cnn_tcn:.4f}, P-값: {p_val_cnn_tcn:.4f}")
