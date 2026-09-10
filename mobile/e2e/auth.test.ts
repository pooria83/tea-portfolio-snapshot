import {by, element, expect} from 'detox';

describe('Auth flow', () => {
  beforeAll(async () => {
    await device.launchApp();
  });

  it('should show phone login screen', async () => {
    await expect(element(by.text('Login'))).toBeVisible();
    await expect(element(by.text('Continue with Google'))).toBeVisible();
  });
});
