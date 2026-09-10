const clipboardMock = {
  setString: jest.fn(async () => {}),
  getString: jest.fn(async () => ''),
  hasString: jest.fn(async () => false),
  setStrings: jest.fn(async () => {}),
  getStrings: jest.fn(async () => []),
  hasStrings: jest.fn(async () => false),
  useClipboard: jest.fn(() => ['', jest.fn()]),
};

export default clipboardMock;
