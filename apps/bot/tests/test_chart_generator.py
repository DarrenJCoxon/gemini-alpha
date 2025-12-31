"""
Unit tests for Chart Generation Service.

Story 2.3: Vision Agent & Chart Generation

Tests cover:
- Candle data to DataFrame conversion
- PNG image generation
- Chart configuration and styling
- Edge cases (empty data, minimal data, large data)
"""

import pytest
from datetime import datetime, timedelta
from services.chart_generator import (
    prepare_chart_data,
    generate_chart_image,
    save_chart_to_file,
    CONTRARIAN_STYLE
)
import tempfile
import os


@pytest.fixture
def sample_candles():
    """Generate 100 sample candles for testing."""
    candles = []
    base_price = 100.0
    base_time = datetime.utcnow() - timedelta(hours=100)

    for i in range(100):
        price = base_price + (i * 0.5) + ((-1) ** i * 3)
        candles.append({
            "timestamp": base_time + timedelta(hours=i),
            "open": price - 1,
            "high": price + 3,
            "low": price - 3,
            "close": price + 0.5,
            "volume": 10000 + (i * 50)
        })
    return candles


@pytest.fixture
def minimal_candles():
    """Generate 50 candles (minimum for SMA50)."""
    candles = []
    base_price = 100.0
    base_time = datetime.utcnow() - timedelta(hours=50)

    for i in range(50):
        price = base_price + (i * 0.3)
        candles.append({
            "timestamp": base_time + timedelta(hours=i),
            "open": price - 0.5,
            "high": price + 1,
            "low": price - 1,
            "close": price,
            "volume": 5000
        })
    return candles


@pytest.fixture
def few_candles():
    """Generate only 10 candles (insufficient for SMA)."""
    candles = []
    base_price = 100.0
    base_time = datetime.utcnow() - timedelta(hours=10)

    for i in range(10):
        price = base_price + (i * 0.2)
        candles.append({
            "timestamp": base_time + timedelta(hours=i),
            "open": price - 0.3,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": 3000
        })
    return candles


@pytest.fixture
def large_candles():
    """Generate 250 candles (more than default 100)."""
    candles = []
    base_price = 100.0
    base_time = datetime.utcnow() - timedelta(hours=250)

    for i in range(250):
        price = base_price + (i * 0.2) + ((-1) ** i * 2)
        candles.append({
            "timestamp": base_time + timedelta(hours=i),
            "open": price - 1,
            "high": price + 2,
            "low": price - 2,
            "close": price + 0.3,
            "volume": 8000 + (i * 20)
        })
    return candles


class TestPrepareChartData:
    """Tests for prepare_chart_data function."""

    def test_valid_data(self, sample_candles):
        """Test conversion with valid candle data."""
        df = prepare_chart_data(sample_candles)
        assert len(df) == 100
        assert 'Open' in df.columns
        assert 'High' in df.columns
        assert 'Low' in df.columns
        assert 'Close' in df.columns
        assert 'Volume' in df.columns

    def test_datetime_index(self, sample_candles):
        """Test that DataFrame has DatetimeIndex."""
        df = prepare_chart_data(sample_candles)
        assert df.index.name == 'timestamp'
        assert hasattr(df.index, 'year')  # DatetimeIndex attribute

    def test_sorted_by_timestamp(self, sample_candles):
        """Test that DataFrame is sorted by timestamp."""
        import random
        shuffled = sample_candles.copy()
        random.shuffle(shuffled)

        df = prepare_chart_data(shuffled)
        assert df.index.is_monotonic_increasing

    def test_numeric_types(self, sample_candles):
        """Test that OHLCV columns are numeric."""
        import pandas as pd
        df = prepare_chart_data(sample_candles)

        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            assert pd.api.types.is_numeric_dtype(df[col])

    def test_empty_list_raises_error(self):
        """Test that empty candles list raises ValueError."""
        with pytest.raises(ValueError, match="No candle data provided"):
            prepare_chart_data([])

    def test_minimal_candles(self, minimal_candles):
        """Test conversion with minimal candle count."""
        df = prepare_chart_data(minimal_candles)
        assert len(df) == 50

    def test_string_numbers_converted(self, sample_candles):
        """Test that string numbers are converted to numeric."""
        # Modify a candle to have string values
        candles_with_strings = sample_candles.copy()
        candles_with_strings[0] = candles_with_strings[0].copy()
        candles_with_strings[0]['close'] = "100.50"
        candles_with_strings[0]['volume'] = "15000"

        df = prepare_chart_data(candles_with_strings)
        import pandas as pd
        assert pd.api.types.is_numeric_dtype(df['Close'])
        assert pd.api.types.is_numeric_dtype(df['Volume'])


class TestGenerateChartImage:
    """Tests for generate_chart_image function."""

    def test_returns_bytes(self, sample_candles):
        """Test that function returns bytes."""
        image_bytes = generate_chart_image(
            candles=sample_candles,
            asset_symbol="TESTUSD",
            num_candles=100
        )
        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 0

    def test_png_magic_bytes(self, sample_candles):
        """Test that output is valid PNG format."""
        image_bytes = generate_chart_image(
            candles=sample_candles,
            asset_symbol="TESTUSD",
            num_candles=100
        )
        # PNG magic bytes
        assert image_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_generate_with_fewer_candles(self, minimal_candles):
        """Test generating chart with minimal candles."""
        image_bytes = generate_chart_image(
            candles=minimal_candles,
            asset_symbol="TESTUSD",
            num_candles=50
        )
        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 0

    def test_truncates_to_num_candles(self, large_candles):
        """Test that chart uses only last N candles."""
        # Generate with 250 candles but only show 100
        image_bytes = generate_chart_image(
            candles=large_candles,
            asset_symbol="TESTUSD",
            num_candles=100
        )
        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 0

    def test_without_volume(self, sample_candles):
        """Test generating chart without volume subplot."""
        image_bytes = generate_chart_image(
            candles=sample_candles,
            asset_symbol="TESTUSD",
            num_candles=100,
            include_volume=False
        )
        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 0

    def test_without_sma(self, sample_candles):
        """Test generating chart without SMA overlays."""
        image_bytes = generate_chart_image(
            candles=sample_candles,
            asset_symbol="TESTUSD",
            num_candles=100,
            include_sma=False
        )
        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 0

    def test_jpeg_format(self, sample_candles):
        """Test generating JPEG format chart."""
        image_bytes = generate_chart_image(
            candles=sample_candles,
            asset_symbol="TESTUSD",
            num_candles=100,
            output_format='jpeg'
        )
        # JPEG magic bytes (FFD8FF)
        assert image_bytes[:3] == b'\xff\xd8\xff'

    def test_custom_dpi(self, sample_candles):
        """Test generating chart with custom DPI."""
        # Lower DPI = smaller file
        low_dpi_bytes = generate_chart_image(
            candles=sample_candles,
            asset_symbol="TESTUSD",
            num_candles=100,
            dpi=75
        )

        high_dpi_bytes = generate_chart_image(
            candles=sample_candles,
            asset_symbol="TESTUSD",
            num_candles=100,
            dpi=200
        )

        # Higher DPI should produce larger file
        assert len(high_dpi_bytes) > len(low_dpi_bytes)

    def test_empty_candles_raises_error(self):
        """Test that empty candles raises ValueError."""
        with pytest.raises(ValueError, match="No candle data provided"):
            generate_chart_image(
                candles=[],
                asset_symbol="TESTUSD",
                num_candles=100
            )

    def test_few_candles_no_sma(self, few_candles):
        """Test chart with too few candles for SMA (should still generate)."""
        image_bytes = generate_chart_image(
            candles=few_candles,
            asset_symbol="TESTUSD",
            num_candles=100,
            include_sma=True  # Will be skipped due to insufficient data
        )
        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 0


class TestSaveChartToFile:
    """Tests for save_chart_to_file function."""

    def test_save_to_temp_file(self, sample_candles):
        """Test saving chart to a temporary file."""
        image_bytes = generate_chart_image(
            candles=sample_candles,
            asset_symbol="TESTUSD",
            num_candles=100
        )

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            filepath = f.name

        try:
            result = save_chart_to_file(image_bytes, filepath)
            assert result == filepath
            assert os.path.exists(filepath)

            # Verify file contents
            with open(filepath, 'rb') as f:
                saved_bytes = f.read()
            assert saved_bytes == image_bytes
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    def test_returns_filepath(self, sample_candles):
        """Test that function returns the filepath."""
        image_bytes = generate_chart_image(
            candles=sample_candles,
            asset_symbol="TESTUSD",
            num_candles=100
        )

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            filepath = f.name

        try:
            result = save_chart_to_file(image_bytes, filepath)
            assert result == filepath
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)


class TestContrarianStyle:
    """Tests for CONTRARIAN_STYLE configuration."""

    def test_style_is_dict(self):
        """Test that style is a valid mplfinance style dict."""
        assert isinstance(CONTRARIAN_STYLE, dict)

    def test_style_has_required_keys(self):
        """Test that style has expected configuration keys."""
        # mplfinance styles have specific keys
        assert 'marketcolors' in CONTRARIAN_STYLE
        assert 'facecolor' in CONTRARIAN_STYLE

    def test_dark_theme_colors(self):
        """Test that style uses dark theme colors."""
        # Background should be dark (near black)
        facecolor = CONTRARIAN_STYLE.get('facecolor', '')
        # #0a0a0a is very dark
        assert facecolor.startswith('#0') or facecolor == '#0a0a0a'
