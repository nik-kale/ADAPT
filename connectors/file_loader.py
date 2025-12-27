"""
Multi-Format File Loader

Supports loading signals from multiple file formats:
- JSONL (JSON Lines)
- JSON (array or single object)
- CSV with configurable column mappings
- stdin for pipeline integration
"""

import json
import csv
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, TextIO
from datetime import datetime
from enum import Enum

from core.signal_normalizer import NormalizedSignal, SignalNormalizer, SignalType


class FileFormat(str, Enum):
    """Supported file formats"""
    JSONL = "jsonl"
    JSON = "json"
    CSV = "csv"
    AUTO = "auto"


class FileLoader:
    """
    Multi-format file loader for signal data.
    
    Features:
    - Auto-detection of file format
    - JSONL, JSON, and CSV support
    - Stdin support for pipelines
    - Configurable CSV column mappings
    """
    
    def __init__(
        self,
        file_format: FileFormat = FileFormat.AUTO,
        csv_timestamp_col: str = "timestamp",
        csv_message_col: str = "message",
        csv_severity_col: str = "severity",
        csv_source_col: str = "source",
        max_lines: Optional[int] = None
    ):
        """
        Initialize file loader.
        
        Args:
            file_format: File format (auto-detect if AUTO)
            csv_timestamp_col: CSV column name for timestamp
            csv_message_col: CSV column name for message
            csv_severity_col: CSV column name for severity
            csv_source_col: CSV column name for source
            max_lines: Maximum lines to read (None = unlimited)
        """
        self.file_format = file_format
        self.csv_timestamp_col = csv_timestamp_col
        self.csv_message_col = csv_message_col
        self.csv_severity_col = csv_severity_col
        self.csv_source_col = csv_source_col
        self.max_lines = max_lines
    
    def load_file(self, file_path: str) -> List[NormalizedSignal]:
        """
        Load signals from file.
        
        Args:
            file_path: Path to file, or "-" for stdin
            
        Returns:
            List of normalized signals
        """
        if file_path == "-":
            return self.load_from_stdin()
        
        path = Path(file_path)
        
        # Detect format if AUTO
        if self.file_format == FileFormat.AUTO:
            detected_format = self._detect_format(path)
        else:
            detected_format = self.file_format
        
        # Load based on format
        if detected_format == FileFormat.JSONL:
            return self.load_jsonl(path)
        elif detected_format == FileFormat.JSON:
            return self.load_json(path)
        elif detected_format == FileFormat.CSV:
            return self.load_csv(path)
        else:
            raise ValueError(f"Unsupported file format: {detected_format}")
    
    def _detect_format(self, path: Path) -> FileFormat:
        """
        Auto-detect file format from extension and content.
        
        Args:
            path: File path
            
        Returns:
            Detected file format
        """
        # Check extension
        ext = path.suffix.lower()
        if ext == '.jsonl':
            return FileFormat.JSONL
        elif ext == '.json':
            return FileFormat.JSON
        elif ext == '.csv':
            return FileFormat.CSV
        
        # Sniff content
        try:
            with open(path, 'r') as f:
                first_line = f.readline().strip()
                
                # Try parsing as JSON
                try:
                    obj = json.loads(first_line)
                    # If it's an array, it's JSON; otherwise JSONL
                    return FileFormat.JSON if isinstance(obj, list) else FileFormat.JSONL
                except json.JSONDecodeError:
                    pass
                
                # Check if it looks like CSV
                if ',' in first_line or '\t' in first_line:
                    return FileFormat.CSV
                
        except Exception:
            pass
        
        # Default to JSONL
        return FileFormat.JSONL
    
    def load_jsonl(self, path: Path) -> List[NormalizedSignal]:
        """
        Load signals from JSONL file.
        
        Args:
            path: Path to JSONL file
            
        Returns:
            List of normalized signals
        """
        signals = []
        
        with open(path, 'r') as f:
            for i, line in enumerate(f):
                if self.max_lines and i >= self.max_lines:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    signal = self._normalize_json_entry(data)
                    signals.append(signal)
                except json.JSONDecodeError as e:
                    # Log warning and continue
                    print(f"Warning: Skipping malformed JSON at line {i+1}: {e}", file=sys.stderr)
                except Exception as e:
                    print(f"Warning: Error processing line {i+1}: {e}", file=sys.stderr)
        
        return signals
    
    def load_json(self, path: Path) -> List[NormalizedSignal]:
        """
        Load signals from JSON file.
        
        Args:
            path: Path to JSON file
            
        Returns:
            List of normalized signals
        """
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Handle single object or array
        if isinstance(data, list):
            entries = data
        else:
            entries = [data]
        
        # Apply max_lines limit
        if self.max_lines:
            entries = entries[:self.max_lines]
        
        signals = []
        for entry in entries:
            try:
                signal = self._normalize_json_entry(entry)
                signals.append(signal)
            except Exception as e:
                print(f"Warning: Error processing entry: {e}", file=sys.stderr)
        
        return signals
    
    def load_csv(self, path: Path) -> List[NormalizedSignal]:
        """
        Load signals from CSV file.
        
        Args:
            path: Path to CSV file
            
        Returns:
            List of normalized signals
        """
        signals = []
        
        with open(path, 'r', newline='') as f:
            # Try to detect delimiter
            sample = f.read(1024)
            f.seek(0)
            
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(sample)
            except csv.Error:
                dialect = csv.excel
            
            reader = csv.DictReader(f, dialect=dialect)
            
            for i, row in enumerate(reader):
                if self.max_lines and i >= self.max_lines:
                    break
                
                try:
                    signal = self._normalize_csv_row(row)
                    signals.append(signal)
                except Exception as e:
                    print(f"Warning: Error processing row {i+1}: {e}", file=sys.stderr)
        
        return signals
    
    def load_from_stdin(self) -> List[NormalizedSignal]:
        """
        Load signals from stdin.
        
        Returns:
            List of normalized signals
        """
        # Try to detect format from first line
        first_line = sys.stdin.readline()
        
        # Check if JSON
        try:
            json.loads(first_line)
            return self._load_jsonl_from_stream(sys.stdin, first_line)
        except json.JSONDecodeError:
            pass
        
        # Check if CSV
        if ',' in first_line or '\t' in first_line:
            return self._load_csv_from_stream(sys.stdin, first_line)
        
        # Default to JSONL
        return self._load_jsonl_from_stream(sys.stdin, first_line)
    
    def _load_jsonl_from_stream(self, stream: TextIO, first_line: str) -> List[NormalizedSignal]:
        """Load JSONL from stream"""
        signals = []
        
        # Process first line
        try:
            data = json.loads(first_line)
            signals.append(self._normalize_json_entry(data))
        except:
            pass
        
        # Process remaining lines
        for i, line in enumerate(stream):
            if self.max_lines and len(signals) >= self.max_lines:
                break
            
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                signals.append(self._normalize_json_entry(data))
            except Exception as e:
                print(f"Warning: Skipping line {i+2}: {e}", file=sys.stderr)
        
        return signals
    
    def _load_csv_from_stream(self, stream: TextIO, first_line: str) -> List[NormalizedSignal]:
        """Load CSV from stream"""
        # Reconstruct stream with first line
        import io
        full_stream = io.StringIO(first_line + stream.read())
        
        signals = []
        reader = csv.DictReader(full_stream)
        
        for i, row in enumerate(reader):
            if self.max_lines and i >= self.max_lines:
                break
            
            try:
                signals.append(self._normalize_csv_row(row))
            except Exception as e:
                print(f"Warning: Error processing row {i+1}: {e}", file=sys.stderr)
        
        return signals
    
    def _normalize_json_entry(self, data: Dict[str, Any]) -> NormalizedSignal:
        """Normalize JSON entry to signal"""
        # Try standard fields first
        if 'signal_type' in data:
            signal_type_str = data['signal_type']
        elif 'type' in data:
            signal_type_str = data['type']
        elif 'level' in data or 'severity' in data:
            signal_type_str = 'log'
        elif 'metric' in data or 'value' in data:
            signal_type_str = 'metric'
        else:
            signal_type_str = 'event'
        
        return SignalNormalizer.normalize_log_entry(
            data,
            source=data.get('source', data.get('service', 'unknown'))
        )
    
    def _normalize_csv_row(self, row: Dict[str, str]) -> NormalizedSignal:
        """Normalize CSV row to signal"""
        # Parse timestamp
        timestamp_str = row.get(self.csv_timestamp_col, '')
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            timestamp = datetime.now()
        
        # Build signal
        return NormalizedSignal(
            signal_type=SignalType.LOG,
            title=row.get(self.csv_message_col, '')[:100],
            description=row.get(self.csv_message_col, ''),
            timestamp=timestamp,
            source=row.get(self.csv_source_col, 'unknown'),
            severity=row.get(self.csv_severity_col, 'medium'),
            metadata={'raw_row': row}
        )


def load_signals(
    file_path: str,
    file_format: FileFormat = FileFormat.AUTO,
    max_lines: Optional[int] = None
) -> List[NormalizedSignal]:
    """
    Convenience function to load signals from file.
    
    Args:
        file_path: Path to file or "-" for stdin
        file_format: File format (auto-detect if AUTO)
        max_lines: Maximum lines to read
        
    Returns:
        List of normalized signals
    """
    loader = FileLoader(file_format=file_format, max_lines=max_lines)
    return loader.load_file(file_path)

