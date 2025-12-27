"""
Tests for Multi-Format File Loader
"""

import pytest
import tempfile
import json
import csv
from pathlib import Path
from datetime import datetime

from connectors.file_loader import FileLoader, FileFormat, load_signals
from core.signal_normalizer import SignalType


class TestFileLoader:
    """Tests for FileLoader class"""
    
    def test_load_jsonl(self):
        """Test loading JSONL file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"message": "Test 1", "timestamp": "2024-01-01T12:00:00", "source": "service-a"}\n')
            f.write('{"message": "Test 2", "timestamp": "2024-01-01T12:01:00", "source": "service-b"}\n')
            temp_path = f.name
        
        try:
            loader = FileLoader(file_format=FileFormat.JSONL)
            signals = loader.load_file(temp_path)
            
            assert len(signals) == 2
            assert signals[0].source == "service-a"
            assert signals[1].source == "service-b"
        finally:
            Path(temp_path).unlink()
    
    def test_load_json_array(self):
        """Test loading JSON array file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            data = [
                {"message": "Test 1", "timestamp": "2024-01-01T12:00:00"},
                {"message": "Test 2", "timestamp": "2024-01-01T12:01:00"}
            ]
            json.dump(data, f)
            temp_path = f.name
        
        try:
            loader = FileLoader(file_format=FileFormat.JSON)
            signals = loader.load_file(temp_path)
            
            assert len(signals) == 2
        finally:
            Path(temp_path).unlink()
    
    def test_load_csv(self):
        """Test loading CSV file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'message', 'severity', 'source'])
            writer.writeheader()
            writer.writerow({
                'timestamp': '2024-01-01T12:00:00',
                'message': 'Test message',
                'severity': 'high',
                'source': 'service-a'
            })
            temp_path = f.name
        
        try:
            loader = FileLoader(file_format=FileFormat.CSV)
            signals = loader.load_file(temp_path)
            
            assert len(signals) == 1
            assert signals[0].source == "service-a"
            assert signals[0].severity == "high"
        finally:
            Path(temp_path).unlink()
    
    def test_auto_detect_jsonl(self):
        """Test auto-detection of JSONL format"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('{"message": "Test"}\n')
            temp_path = f.name
        
        try:
            loader = FileLoader(file_format=FileFormat.AUTO)
            detected = loader._detect_format(Path(temp_path))
            
            assert detected == FileFormat.JSONL
        finally:
            Path(temp_path).unlink()
    
    def test_max_lines_limit(self):
        """Test max_lines parameter"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for i in range(100):
                f.write(f'{{"message": "Test {i}"}}\n')
            temp_path = f.name
        
        try:
            loader = FileLoader(file_format=FileFormat.JSONL, max_lines=10)
            signals = loader.load_file(temp_path)
            
            assert len(signals) == 10
        finally:
            Path(temp_path).unlink()
    
    def test_malformed_json_handling(self):
        """Test handling of malformed JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"valid": "json"}\n')
            f.write('{invalid json}\n')
            f.write('{"another": "valid"}\n')
            temp_path = f.name
        
        try:
            loader = FileLoader(file_format=FileFormat.JSONL)
            signals = loader.load_file(temp_path)
            
            # Should skip malformed line
            assert len(signals) == 2
        finally:
            Path(temp_path).unlink()
    
    def test_custom_csv_columns(self):
        """Test custom CSV column mapping"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['time', 'msg', 'sev', 'svc'])
            writer.writeheader()
            writer.writerow({
                'time': '2024-01-01T12:00:00',
                'msg': 'Test',
                'sev': 'high',
                'svc': 'api'
            })
            temp_path = f.name
        
        try:
            loader = FileLoader(
                file_format=FileFormat.CSV,
                csv_timestamp_col='time',
                csv_message_col='msg',
                csv_severity_col='sev',
                csv_source_col='svc'
            )
            signals = loader.load_file(temp_path)
            
            assert len(signals) == 1
            assert signals[0].source == "api"
        finally:
            Path(temp_path).unlink()


class TestConvenienceFunctions:
    """Tests for convenience functions"""
    
    def test_load_signals_convenience(self):
        """Test load_signals convenience function"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"message": "Test"}\n')
            temp_path = f.name
        
        try:
            signals = load_signals(temp_path)
            assert len(signals) == 1
        finally:
            Path(temp_path).unlink()

