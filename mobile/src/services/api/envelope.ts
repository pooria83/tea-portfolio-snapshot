import type {AxiosResponse} from 'axios';

export const unwrapEnvelope = <T>(response: AxiosResponse<unknown>): T => {
  const body = response.data;
  if (
    body !== null &&
    typeof body === 'object' &&
    'success' in body &&
    body.success === true &&
    'data' in body
  ) {
    return (body as {data: T}).data;
  }
  throw new Error('Invalid API envelope');
};
