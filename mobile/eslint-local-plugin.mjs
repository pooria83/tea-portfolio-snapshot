const ASYNC_STATE_PROPS = [
  'isSuccess',
  'isError',
  'isLoading',
  'isFetching',
  'isRefetching',
  'isPaused',
  'data',
  'error',
  'status',
];

const plugin = {
  rules: {
    'no-direct-result-current-assertion': {
      meta: {
        type: 'problem',
        docs: {
          description:
            'Forbid asserting async query/mutation state on result.current outside waitFor() or act()',
        },
        messages: {
          direct:
            'Async state assertion `result.current.{{prop}}` must be wrapped in waitFor() or act() — direct assertions race with React state updates and fail only on slow CI runners.',
        },
        schema: [],
      },
      create(context) {
        function isInsideCall(node, calleeName) {
          let current = node.parent;
          while (current) {
            if (
              current.type === 'CallExpression' &&
              current.callee.type === 'Identifier' &&
              current.callee.name === calleeName
            ) {
              return true;
            }
            current = current.parent;
          }
          return false;
        }

        return {
          CallExpression(node) {
            const {callee, arguments: args} = node;
            if (callee.type !== 'Identifier' || callee.name !== 'expect') {
              return;
            }
            const arg = args[0];
            if (!arg || arg.type !== 'MemberExpression') {
              return;
            }
            const prop = arg.property;
            if (prop.type !== 'Identifier' || !ASYNC_STATE_PROPS.includes(prop.name)) {
              return;
            }
            let object = arg;
            while (object.object && object.object.type === 'MemberExpression') {
              object = object.object;
            }
            if (
              object.object.type !== 'Identifier' ||
              object.object.name !== 'result'
            ) {
              return;
            }
            if (isInsideCall(node, 'waitFor') || isInsideCall(node, 'act')) {
              return;
            }
            context.report({
              node: arg,
              messageId: 'direct',
              data: {prop: prop.name},
            });
          },
        };
      },
    },
  },
};

export default plugin;
