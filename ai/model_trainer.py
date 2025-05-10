import logging
import os
import json
import time
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import tensorflow as tf
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import Dense, LSTM, Dropout, Input, MultiHeadAttention, LayerNormalization
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

class ModelTrainer:
    """
    Trainer for AI prediction models used in arbitrage
    """
    
    def __init__(self, config=None):
        """
        Initialize the ModelTrainer
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        
        # Set hyperparameters from config or defaults
        self.batch_size = int(os.environ.get("AI_BATCH_SIZE", "32"))
        self.epochs = int(os.environ.get("AI_EPOCHS", "100"))
        self.validation_split = float(os.environ.get("AI_VALIDATION_SPLIT", "0.2"))
        self.sequence_length = int(os.environ.get("AI_SEQUENCE_LENGTH", "10"))
        self.learning_rate = float(os.environ.get("AI_LEARNING_RATE", "0.001"))
        
        # Model architecture type
        self.model_type = os.environ.get("AI_MODEL_TYPE", "LSTM").upper()
        
        # Feature engineering settings
        self.feature_columns = [
            'price_diff_pct', 'buy_price', 'sell_price',
            'buy_liquidity', 'sell_liquidity',
            'hour_of_day', 'day_of_week',
            'volatility', 'volume'
        ]
        
        # Output paths
        self.models_dir = os.environ.get("AI_MODELS_DIR", "ai/models")
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Scaler for feature normalization
        self.scaler = StandardScaler()
        
    def load_training_data(self, data_path=None):
        """
        Load training data from file or database
        
        Args:
            data_path: Path to data file (CSV or JSON)
            
        Returns:
            Pandas DataFrame with loaded data
        """
        try:
            # Load from file if specified
            if data_path and os.path.exists(data_path):
                # Determine file type from extension
                if data_path.endswith('.csv'):
                    return pd.read_csv(data_path)
                elif data_path.endswith('.json'):
                    return pd.read_json(data_path)
                else:
                    logger.error(f"Unsupported data file format: {data_path}")
                    return None
                    
            # Otherwise, query from database
            from api.app import app
            from models import ArbitrageOpportunity, ArbitrageExecution
            
            with app.app_context():
                # Join opportunities with executions to get success/fail labels
                query = """
                SELECT 
                    o.token_pair, o.source_dex, o.target_dex, 
                    o.source_price, o.target_price, o.price_difference_percent,
                    o.estimated_profit_usd, o.network, o.created_at,
                    CASE WHEN e.status = 'success' THEN 1 ELSE 0 END as success,
                    e.actual_profit_usd, e.gas_cost_usd, e.net_profit_usd
                FROM arbitrage_opportunity o
                LEFT JOIN arbitrage_execution e ON o.id = e.opportunity_id
                WHERE o.created_at > DATE_SUB(NOW(), INTERVAL 30 DAY)
                ORDER BY o.created_at DESC
                """
                
                # Execute the query and load to DataFrame
                import sqlite3
                import pandas as pd
                
                # Get DB connection from app
                conn = sqlite3.connect(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
                df = pd.read_sql_query(query, conn)
                conn.close()
                
                if df.empty:
                    logger.warning("No training data found in database")
                    return None
                    
                logger.info(f"Loaded {len(df)} rows of training data from database")
                return df
                
        except Exception as e:
            logger.error(f"Error loading training data: {str(e)}")
            return None
            
    def preprocess_data(self, df):
        """
        Preprocess data for training
        
        Args:
            df: Pandas DataFrame with raw data
            
        Returns:
            X_train, X_test, y_train, y_test for model training
        """
        try:
            if df is None or df.empty:
                logger.error("No data to preprocess")
                return None
                
            # Drop rows with missing values
            df = df.dropna(subset=[
                'price_difference_percent', 'source_price', 'target_price', 
                'success', 'actual_profit_usd'
            ])
            
            # Engineer features
            df['hour_of_day'] = pd.to_datetime(df['created_at']).dt.hour / 24.0
            df['day_of_week'] = pd.to_datetime(df['created_at']).dt.dayofweek / 6.0
            
            # Use provided liquidity if available, otherwise default to 0
            if 'source_liquidity' not in df.columns:
                df['source_liquidity'] = 0
            if 'target_liquidity' not in df.columns:
                df['target_liquidity'] = 0
                
            # Calculate profit accuracy (ratio of actual to estimated)
            df['profit_accuracy'] = df.apply(
                lambda row: row['actual_profit_usd'] / row['estimated_profit_usd'] 
                if row['estimated_profit_usd'] > 0 else 0,
                axis=1
            )
            
            # Prepare features and labels
            X = df[[
                'price_difference_percent', 
                'source_price', 
                'target_price',
                'source_liquidity',
                'target_liquidity',
                'hour_of_day',
                'day_of_week'
            ]].values
            
            # Labels: [success probability, profit multiplier]
            y = df[['success', 'profit_accuracy']].values
            
            # Normalize features
            X = self.scaler.fit_transform(X)
            
            # Split into training and test sets
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.validation_split, random_state=42
            )
            
            return X_train, X_test, y_train, y_test
            
        except Exception as e:
            logger.error(f"Error preprocessing data: {str(e)}")
            return None
            
    def create_lstm_model(self, input_shape):
        """
        Create an LSTM model for opportunity prediction
        
        Args:
            input_shape: Shape of input features
            
        Returns:
            Compiled model
        """
        model = Sequential()
        
        # LSTM layers
        model.add(LSTM(64, return_sequences=True, input_shape=(input_shape,)))
        model.add(Dropout(0.2))
        model.add(LSTM(32))
        model.add(Dropout(0.2))
        
        # Output layers - two outputs:
        # 1. Success probability (0-1)
        # 2. Profit multiplier (how much of the estimated profit will be realized)
        model.add(Dense(16, activation='relu'))
        model.add(Dense(2, activation='sigmoid'))
        
        # Compile model
        model.compile(
            optimizer=Adam(learning_rate=self.learning_rate),
            loss='mse',
            metrics=['mae']
        )
        
        return model
        
    def create_transformer_model(self, input_shape):
        """
        Create a Transformer model for opportunity prediction
        
        Args:
            input_shape: Shape of input features
            
        Returns:
            Compiled model
        """
        inputs = Input(shape=(input_shape,))
        
        # Self-attention mechanism
        attention_output = MultiHeadAttention(
            num_heads=4, key_dim=input_shape
        )(inputs, inputs)
        
        # Skip connection and normalization
        x = LayerNormalization()(inputs + attention_output)
        
        # Dense layers
        x = Dense(64, activation='relu')(x)
        x = Dropout(0.2)(x)
        x = Dense(32, activation='relu')(x)
        x = Dropout(0.2)(x)
        
        # Output layers - two outputs:
        # 1. Success probability (0-1)
        # 2. Profit multiplier
        outputs = Dense(2, activation='sigmoid')(x)
        
        # Create and compile model
        model = Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer=Adam(learning_rate=self.learning_rate),
            loss='mse',
            metrics=['mae']
        )
        
        return model
        
    def train_model(self, data_path=None):
        """
        Train a new prediction model
        
        Args:
            data_path: Optional path to training data
            
        Returns:
            Trained model or None if training failed
        """
        try:
            # Load and preprocess data
            df = self.load_training_data(data_path)
            if df is None:
                logger.error("Failed to load training data")
                return None
                
            processed_data = self.preprocess_data(df)
            if processed_data is None:
                logger.error("Failed to preprocess data")
                return None
                
            X_train, X_test, y_train, y_test = processed_data
            
            # Create model based on type
            input_dim = X_train.shape[1]
            if self.model_type == 'LSTM':
                # Reshape data for LSTM [samples, time steps, features]
                X_train = X_train.reshape(X_train.shape[0], 1, X_train.shape[1])
                X_test = X_test.reshape(X_test.shape[0], 1, X_test.shape[1])
                model = self.create_lstm_model(X_train.shape[1:])
            elif self.model_type == 'TRANSFORMER':
                model = self.create_transformer_model(input_dim)
            else:
                logger.error(f"Unsupported model type: {self.model_type}")
                return None
                
            # Create callbacks
            timestamp = int(time.time())
            model_path = os.path.join(self.models_dir, f"arbitrage_model_{timestamp}.h5")
            
            callbacks = [
                EarlyStopping(patience=10, restore_best_weights=True),
                ModelCheckpoint(
                    filepath=model_path,
                    save_best_only=True
                )
            ]
            
            # Train model
            logger.info(f"Starting model training with {len(X_train)} samples")
            history = model.fit(
                X_train, y_train,
                validation_data=(X_test, y_test),
                epochs=self.epochs,
                batch_size=self.batch_size,
                callbacks=callbacks,
                verbose=1
            )
            
            # Evaluate model
            evaluation = model.evaluate(X_test, y_test)
            
            # Log results
            logger.info(f"Model training completed: Loss={evaluation[0]:.4f}, MAE={evaluation[1]:.4f}")
            
            # Save model info
            model_info = {
                'timestamp': timestamp,
                'type': self.model_type,
                'loss': float(evaluation[0]),
                'mae': float(evaluation[1]),
                'input_shape': list(X_train.shape[1:]),
                'feature_columns': self.feature_columns,
                'path': model_path,
                'training_samples': len(X_train)
            }
            
            info_path = os.path.join(self.models_dir, f"model_info_{timestamp}.json")
            with open(info_path, 'w') as f:
                json.dump(model_info, f)
                
            logger.info(f"Model saved to {model_path}")
            
            # Save scaler for future use
            scaler_path = os.path.join(self.models_dir, f"scaler_{timestamp}.pkl")
            import pickle
            with open(scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
                
            return model
            
        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            return None
            
    def get_best_model_path(self):
        """
        Get path to the best trained model
        
        Returns:
            Path to best model file or None if not found
        """
        try:
            # Look for model info files
            info_files = [f for f in os.listdir(self.models_dir) if f.startswith("model_info_") and f.endswith(".json")]
            
            if not info_files:
                logger.warning("No trained models found")
                return None
                
            # Load model info
            best_model = None
            best_score = float('inf')
            
            for info_file in info_files:
                info_path = os.path.join(self.models_dir, info_file)
                with open(info_path, 'r') as f:
                    info = json.load(f)
                    
                # Check if model file exists
                if not os.path.exists(info['path']):
                    continue
                    
                # Compare models based on loss
                if info['loss'] < best_score:
                    best_score = info['loss']
                    best_model = info
                    
            if best_model:
                logger.info(f"Best model found: {best_model['path']} (Loss: {best_score:.4f})")
                return best_model['path']
            else:
                logger.warning("No valid model files found")
                return None
                
        except Exception as e:
            logger.error(f"Error finding best model: {str(e)}")
            return None
