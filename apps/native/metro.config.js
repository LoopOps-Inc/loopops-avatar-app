const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, '../..');

const config = getDefaultConfig(projectRoot);

// 1. Monitor all files inside the monorepo
config.watchFolders = [workspaceRoot];

// 2. Allow Metro to resolve modules using the monorepo's node_modules hierarchy
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, 'node_modules'),
  path.resolve(workspaceRoot, 'node_modules'),
];

// 3. Prevent duplicate lookup collisions
config.resolver.disableHierarchicalLookup = false;

config.resolver.resolveRequest = (context, moduleName, platform) => {
  const reactRoot = path.join(projectRoot, 'node_modules', 'react');
  if (moduleName === 'react') {
    return { type: 'sourceFile', filePath: path.join(reactRoot, 'index.js') };
  }
  if (moduleName.startsWith('react/')) {
    const filePath = path.join(reactRoot, moduleName.slice('react/'.length));
    if (require('fs').existsSync(filePath)) {
      return { type: 'sourceFile', filePath };
    }
  }
  return context.resolveRequest(context, moduleName, platform);
};

module.exports = config;
