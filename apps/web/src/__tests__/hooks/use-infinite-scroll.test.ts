/**
 * @jest-environment jsdom
 */

import { renderHook } from '@testing-library/react';
import { useInfiniteScroll } from '@/hooks/use-infinite-scroll';

describe('useInfiniteScroll Hook', () => {
  describe('Initialization', () => {
    it('should return a ref object', () => {
      const onLoadMore = jest.fn();
      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      expect(result.current.loadMoreRef).toBeDefined();
      expect(result.current.loadMoreRef).toHaveProperty('current');
    });

    it('should have null current initially', () => {
      const onLoadMore = jest.fn();
      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      expect(result.current.loadMoreRef.current).toBeNull();
    });
  });

  describe('Hook Configuration', () => {
    it('should accept hasMore true', () => {
      const onLoadMore = jest.fn();
      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      expect(result.current.loadMoreRef).toBeDefined();
    });

    it('should accept hasMore false', () => {
      const onLoadMore = jest.fn();
      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: false,
          isLoading: false,
        })
      );

      expect(result.current.loadMoreRef).toBeDefined();
    });

    it('should accept isLoading true', () => {
      const onLoadMore = jest.fn();
      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: true,
        })
      );

      expect(result.current.loadMoreRef).toBeDefined();
    });

    it('should accept custom threshold', () => {
      const onLoadMore = jest.fn();
      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
          threshold: 500,
        })
      );

      expect(result.current.loadMoreRef).toBeDefined();
    });
  });

  describe('Callback Preservation', () => {
    it('should preserve callback reference', () => {
      const onLoadMore = jest.fn();
      const { result, rerender } = renderHook(
        ({ onLoadMore, hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { onLoadMore, hasMore: true } }
      );

      const initialRef = result.current.loadMoreRef;

      rerender({ onLoadMore, hasMore: false });

      // Ref should be the same object
      expect(result.current.loadMoreRef).toBe(initialRef);
    });
  });

  describe('Rerender Handling', () => {
    it('should handle hasMore change from true to false', () => {
      const onLoadMore = jest.fn();
      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: true } }
      );

      expect(result.current.loadMoreRef).toBeDefined();

      rerender({ hasMore: false });

      expect(result.current.loadMoreRef).toBeDefined();
    });

    it('should handle isLoading change from false to true', () => {
      const onLoadMore = jest.fn();
      const { result, rerender } = renderHook(
        ({ isLoading }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore: true,
            isLoading,
          }),
        { initialProps: { isLoading: false } }
      );

      expect(result.current.loadMoreRef).toBeDefined();

      rerender({ isLoading: true });

      expect(result.current.loadMoreRef).toBeDefined();
    });
  });

  describe('Unmount Behavior', () => {
    it('should not throw on unmount', () => {
      const onLoadMore = jest.fn();
      const { unmount } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      expect(() => unmount()).not.toThrow();
    });
  });
});
