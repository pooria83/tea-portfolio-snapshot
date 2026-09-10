import {render, act, waitFor} from '@testing-library/react-native';
import {PaperProvider, MD3LightTheme} from 'react-native-paper';
import * as React from 'react';
import {
  RetryingThumbnail,
  normalizeSrc,
} from '../../../src/components/chat/RetryingThumbnail';

const wrapper = ({children}: {children: React.ReactNode}) => (
  <PaperProvider theme={MD3LightTheme}>{children}</PaperProvider>
);

afterEach(() => {
  jest.useRealTimers();
});

describe('normalizeSrc', () => {
  it('rewrites storage hosts to the image optimizer with the requested width', () => {
    expect(
      normalizeSrc('https://portfolio.example.invalid/product-graph/img.jpg', 256),
    ).toBe(
      'https://portfolio.example.invalid/_next/image?url=https%3A%2F%portfolio.example.invalid%2Fproduct-graph%2Fimg.jpg&w=256&q=75',
    );
  });

  it('rewrites the production storage host to the optimizer', () => {
    expect(
      normalizeSrc('https://portfolio.example.invalid/product-graph/img.jpg'),
    ).toContain(
      'portfolio.example.invalid/_next/image?url=https%3A%2F%portfolio.example.invalid%2F',
    );
  });

  it('leaves foreign hosts untouched', () => {
    expect(normalizeSrc('https://images.example.com/img.jpg')).toBe(
      'https://images.example.com/img.jpg',
    );
  });

  it('rounds widths up to the nearest allowed optimizer width', () => {
    expect(normalizeSrc('https://portfolio.example.invalid/img.jpg', 48)).toContain(
      '&w=64&',
    );
    expect(
      normalizeSrc('https://portfolio.example.invalid/img.jpg', 300),
    ).toContain('&w=640&');
  });
});

describe('RetryingThumbnail', () => {
  it('renders the image through the optimizer with a rounded width', async () => {
    const {getByLabelText} = await render(
      <RetryingThumbnail
        src="https://portfolio.example.invalid/product-graph/a.jpg"
        alt="Product A"
        size={48}
      />,
      {wrapper},
    );

    const image = getByLabelText('Product A') as unknown as {
      props: {source?: {uri?: string}};
    };
    expect(image.props.source?.uri).toBe(
      'https://portfolio.example.invalid/_next/image?url=https%3A%2F%portfolio.example.invalid%2Fproduct-graph%2Fa.jpg&w=64&q=75',
    );
  });

  it('renders non-optimizable sources untouched', async () => {
    const {getByLabelText} = await render(
      <RetryingThumbnail
        src="https://images.example.com/a.jpg"
        alt="Product A"
      />,
      {wrapper},
    );

    const image = getByLabelText('Product A') as unknown as {
      props: {source?: {uri?: string}};
    };
    expect(image.props.source?.uri).toBe('https://images.example.com/a.jpg');
  });

  it('falls back to the raw URL after the optimized URL fails', async () => {
    jest.useFakeTimers();
    const rawUrl = 'https://portfolio.example.invalid/product-graph/b.jpg';
    const {getByLabelText, getByText} = await render(
      <RetryingThumbnail src={rawUrl} alt="Broken" />,
      {wrapper},
    );

    for (let attempt = 0; attempt < 4; attempt += 1) {
      const image = getByLabelText('Broken');
      await act(async () => {
        image.props.onError();
      });
      await act(async () => {
        jest.advanceTimersByTime(5000);
      });
    }

    await waitFor(() => {
      const fallback = getByLabelText('Broken') as unknown as {
        props: {source?: {uri?: string}};
      };
      expect(fallback.props.source?.uri).toBe(rawUrl);
    });
    expect(() => getByText('image')).toThrow();
  });

  it('falls back to the placeholder when the raw URL also fails', async () => {
    jest.useFakeTimers();
    const rawUrl = 'https://portfolio.example.invalid/product-graph/c.jpg';
    const {getByLabelText, getByText} = await render(
      <RetryingThumbnail src={rawUrl} alt="Broken" />,
      {wrapper},
    );

    for (let attempt = 0; attempt < 4; attempt += 1) {
      const image = getByLabelText('Broken');
      await act(async () => {
        image.props.onError();
      });
      await act(async () => {
        jest.advanceTimersByTime(5000);
      });
    }

    await waitFor(() => {
      const fallback = getByLabelText('Broken') as unknown as {
        props: {source?: {uri?: string}};
      };
      expect(fallback.props.source?.uri).toBe(rawUrl);
    });

    const rawImage = getByLabelText('Broken');
    await act(async () => {
      rawImage.props.onError();
    });
    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    await waitFor(() => expect(getByText('image')).toBeTruthy());
  });

  it('retries after an image error and falls back to the placeholder for non-optimizable sources', async () => {
    jest.useFakeTimers();
    const {getByLabelText, getByText} = await render(
      <RetryingThumbnail src="https://images.example.com/b.jpg" alt="Broken" />,
      {wrapper},
    );

    for (let attempt = 0; attempt < 4; attempt += 1) {
      const image = getByLabelText('Broken');
      await act(async () => {
        image.props.onError();
      });
      await act(async () => {
        jest.advanceTimersByTime(5000);
      });
    }

    await waitFor(() => expect(getByText('image')).toBeTruthy());
  });

  it('retries with a fresh image element after the backoff delay', async () => {
    jest.useFakeTimers();
    const {getByLabelText} = await render(
      <RetryingThumbnail
        src="https://images.example.com/c.jpg"
        alt="Pending"
      />,
      {wrapper},
    );

    const first = getByLabelText('Pending');
    expect(first.type).toBe('Image');
    expect(first.props.key ?? 0).toBe(0);

    await act(async () => {
      first.props.onError();
    });
    await act(async () => {
      jest.advanceTimersByTime(499);
    });
    expect(() => getByLabelText('Pending')).toThrow();

    await act(async () => {
      jest.advanceTimersByTime(1);
    });

    const retried = getByLabelText('Pending');
    expect(retried.type).toBe('Image');
    expect(retried.props.source?.uri).toBe('https://images.example.com/c.jpg');
    expect(retried).not.toBe(first);
  });

  it('shows a loading spinner while the image loads and hides it on load end', async () => {
    const {getByLabelText, container} = await render(
      <RetryingThumbnail
        src="https://portfolio.example.invalid/product-graph/a.jpg"
        alt="Spinner"
      />,
      {wrapper},
    );

    expect(
      container.queryAll((node) => node.type === 'ActivityIndicator'),
    ).toHaveLength(0);

    const image = getByLabelText('Spinner') as unknown as {
      props: {onLoadStart?: () => void; onLoadEnd?: () => void};
    };
    await act(async () => {
      image.props.onLoadStart?.();
    });
    expect(
      container.queryAll((node) => node.type === 'ActivityIndicator'),
    ).toHaveLength(1);

    await act(async () => {
      image.props.onLoadEnd?.();
    });
    expect(
      container.queryAll((node) => node.type === 'ActivityIndicator'),
    ).toHaveLength(0);
  });

  it('shows a spinner placeholder during the backoff retry delay', async () => {
    jest.useFakeTimers();
    const {getByLabelText, container} = await render(
      <RetryingThumbnail
        src="https://images.example.com/b.jpg"
        alt="Retrying"
      />,
      {wrapper},
    );

    const image = getByLabelText('Retrying') as unknown as {
      props: {onError?: () => void};
    };
    await act(async () => {
      image.props.onError?.();
    });

    expect(
      container.queryAll((node) => node.type === 'ActivityIndicator'),
    ).toHaveLength(1);

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });
  });
});
