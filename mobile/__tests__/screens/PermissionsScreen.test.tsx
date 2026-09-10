import {render, userEvent, waitFor} from '@testing-library/react-native';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import * as React from 'react';
import {PaperProvider, MD3LightTheme} from 'react-native-paper';
import {check, openSettings, request} from 'react-native-permissions';

import PermissionsScreen from '../../src/app/screens/PermissionsScreen';
import {storage} from '../../src/services/storage';

jest.mock('react-native-permissions');

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {queries: {retry: false}},
  });
  return ({children}: {children: React.ReactNode}) => (
    <QueryClientProvider client={queryClient}>
      <PaperProvider theme={MD3LightTheme}>{children}</PaperProvider>
    </QueryClientProvider>
  );
};

const navigation = {
  goBack: jest.fn(),
} as unknown as Parameters<typeof PermissionsScreen>[0]['navigation'];

const mockedCheck = check as jest.Mock;
const mockedRequest = request as jest.Mock;
const mockedOpenSettings = openSettings as jest.Mock;

describe('PermissionsScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedCheck.mockResolvedValue('granted');
    mockedRequest.mockResolvedValue('granted');
    void storage.setNotificationsOnboarded();
  });

  it('renders the three permission rows', async () => {
    mockedCheck.mockResolvedValue('denied');
    const {getByText, getAllByText} = await render(
      <PermissionsScreen navigation={navigation} />,
      {wrapper: createWrapper()},
    );

    expect(getByText('notificationsTitle')).toBeTruthy();
    expect(getByText('locationTitle')).toBeTruthy();
    expect(getByText('microphoneTitle')).toBeTruthy();
    await waitFor(() => {
      expect(getByText('granted')).toBeTruthy();
      expect(getAllByText('denied').length).toBe(2);
    });
  });

  it('shows granted status for already-granted permissions and hides Allow', async () => {
    const {getAllByText, queryAllByText} = await render(
      <PermissionsScreen navigation={navigation} />,
      {wrapper: createWrapper()},
    );

    await waitFor(() => {
      expect(getAllByText('granted').length).toBeGreaterThanOrEqual(3);
      expect(queryAllByText('allow').length).toBe(0);
    });
  });

  it('opens system settings when the request ends blocked', async () => {
    mockedCheck.mockResolvedValue('denied');
    mockedRequest.mockResolvedValue('blocked');
    const user = userEvent.setup();
    const {getAllByText} = await render(
      <PermissionsScreen navigation={navigation} />,
      {wrapper: createWrapper()},
    );

    const allowButtons = await waitFor(() => getAllByText('allow'));
    expect(allowButtons.length).toBeGreaterThan(0);
    await user.press(allowButtons[1] ?? allowButtons[0]!);
    await waitFor(() => {
      expect(mockedOpenSettings).toHaveBeenCalled();
    });
  });

  it('walks back via Done', async () => {
    const user = userEvent.setup();
    const {getByText} = await render(
      <PermissionsScreen navigation={navigation} />,
      {wrapper: createWrapper()},
    );
    await user.press(getByText('done'));
    expect(navigation.goBack).toHaveBeenCalled();
  });
});
