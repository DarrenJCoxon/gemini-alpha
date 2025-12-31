"""
Chart Generation Service for Vision Agent.

Story 2.3: Vision Agent & Chart Generation

This module generates candlestick chart images from OHLCV candle data
using mplfinance for visual analysis by the Gemini Vision model.

Features:
    - Dark "Institutional Dark" theme matching UI
    - SMA 50/200 overlays
    - Volume subplot
    - Configurable candle count and DPI
"""

# Use Agg backend for headless server environments
import matplotlib
matplotlib.use('Agg')

import io
from typing import Any, Dict, List

import mplfinance as mpf
import pandas as pd
import matplotlib.pyplot as plt


# Dark theme matching "Institutional Dark" UI
CONTRARIAN_STYLE = mpf.make_mpf_style(
    base_mpf_style='nightclouds',
    marketcolors=mpf.make_marketcolors(
        up='#00FF88',      # Profit green
        down='#FF4444',    # Loss red
        edge='inherit',
        wick='inherit',
        volume='inherit'
    ),
    facecolor='#0a0a0a',   # Near black background
    edgecolor='#1a1a1a',
    figcolor='#0a0a0a',
    gridcolor='#1a1a1a',
    gridstyle='--',
    gridaxis='both',
    y_on_right=True,
    rc={
        'font.size': 10,
        'axes.labelsize': 10,
        'axes.titlesize': 12
    }
)


def prepare_chart_data(candles: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert candle data to mplfinance-compatible DataFrame.

    mplfinance requires:
    - DatetimeIndex
    - Columns: Open, High, Low, Close, Volume (capitalized)

    Args:
        candles: List of candle dictionaries with keys:
            timestamp, open, high, low, close, volume

    Returns:
        pd.DataFrame: DataFrame with DatetimeIndex and OHLCV columns

    Raises:
        ValueError: If candles list is empty
    """
    if not candles:
        raise ValueError("No candle data provided")

    df = pd.DataFrame(candles)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df = df.sort_index()

    # Rename to mplfinance expected columns (capitalized)
    df = df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    })

    # Ensure numeric types
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def generate_chart_image(
    candles: List[Dict[str, Any]],
    asset_symbol: str,
    num_candles: int = 100,
    include_volume: bool = True,
    include_sma: bool = True,
    output_format: str = 'png',
    dpi: int = 150
) -> bytes:
    """
    Generate a candlestick chart image from candle data.

    Creates a professional-looking candlestick chart with optional
    SMA overlays and volume subplot. The image is generated in memory
    and returned as bytes suitable for the Vision API.

    Args:
        candles: List of OHLCV candle dicts with keys:
            timestamp, open, high, low, close, volume
        asset_symbol: Asset symbol for chart title (e.g., "SOLUSD")
        num_candles: Number of recent candles to display (default: 100)
        include_volume: Show volume subplot (default: True)
        include_sma: Overlay SMA 50/200 lines (default: True)
        output_format: Image format - 'png' or 'jpeg' (default: 'png')
        dpi: Image resolution (default: 150, ~1800x1200 pixels)

    Returns:
        bytes: Image bytes in the specified format

    Raises:
        ValueError: If candles list is empty
    """
    # Prepare data
    df = prepare_chart_data(candles)

    # Take last N candles
    if len(df) > num_candles:
        df = df.tail(num_candles)

    # Build addplot list for overlays
    addplots = []

    if include_sma and len(df) >= 50:
        sma_50 = df['Close'].rolling(window=50).mean()
        addplots.append(mpf.make_addplot(sma_50, color='#FFD700', width=1.5))

    if include_sma and len(df) >= 200:
        sma_200 = df['Close'].rolling(window=200).mean()
        addplots.append(mpf.make_addplot(sma_200, color='#FF69B4', width=1.5))

    # Create in-memory buffer
    buf = io.BytesIO()

    # Build plot kwargs
    plot_kwargs = {
        'type': 'candle',
        'style': CONTRARIAN_STYLE,
        'title': f'{asset_symbol} - Last {len(df)} Candles',
        'ylabel': 'Price (USD)',
        'ylabel_lower': 'Volume',
        'volume': include_volume,
        'figsize': (12, 8),
        'returnfig': True,
        'savefig': dict(fname=buf, format=output_format, dpi=dpi, bbox_inches='tight')
    }

    # Only add addplot if we have overlays (mplfinance doesn't accept None)
    if addplots:
        plot_kwargs['addplot'] = addplots

    # Generate chart
    fig, axes = mpf.plot(df, **plot_kwargs)

    # Get bytes
    buf.seek(0)
    image_bytes = buf.read()
    buf.close()

    # Close figure to free memory (important for long-running process)
    plt.close(fig)

    return image_bytes


def save_chart_to_file(
    image_bytes: bytes,
    filepath: str
) -> str:
    """
    Save chart image to file for debugging.

    Utility function to save generated chart images to disk
    for visual inspection during development and debugging.

    Args:
        image_bytes: PNG or JPEG image bytes
        filepath: Destination file path

    Returns:
        str: The filepath where image was saved
    """
    with open(filepath, 'wb') as f:
        f.write(image_bytes)
    return filepath
