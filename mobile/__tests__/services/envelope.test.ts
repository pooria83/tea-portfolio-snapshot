import {type AxiosResponse} from 'axios';
import {unwrapEnvelope} from '../../src/services/api/envelope';

const makeResponse = (data: unknown): AxiosResponse<unknown> =>
  ({
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: {},
  }) as AxiosResponse;

describe('unwrapEnvelope', () => {
  it('returns the payload of a valid envelope', () => {
    const response = makeResponse({success: true, data: {id: 'user-1'}});

    expect(unwrapEnvelope<{id: string}>(response)).toEqual({id: 'user-1'});
  });

  it('returns falsy payloads when present', () => {
    const response = makeResponse({success: true, data: null});

    expect(unwrapEnvelope<null>(response)).toBeNull();
  });

  it('throws when the response is not an object', () => {
    expect(() => unwrapEnvelope(makeResponse('nope'))).toThrow(
      'Invalid API envelope',
    );
  });

  it('throws when success is false', () => {
    const response = makeResponse({
      success: false,
      error: {message: 'nope'},
    });

    expect(() => unwrapEnvelope(makeResponse(response.data))).toThrow(
      'Invalid API envelope',
    );
  });

  it('throws when the data field is missing', () => {
    const response = makeResponse({success: true});

    expect(() => unwrapEnvelope(makeResponse(response.data))).toThrow(
      'Invalid API envelope',
    );
  });
});
