import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { nodePolyfills } from 'vite-plugin-node-polyfills'

/**
 * Ketcher bundles still contain a raw:
 *
 *   require("raphael")
 *
 * which is invalid in a browser ESM bundle.
 *
 * Convert that one CommonJS call into a normal ESM import before Rollup
 * processes the Ketcher module.
 */
function fixKetcherRaphael(): Plugin {
  return {
    name: 'fix-ketcher-raphael-require',
    enforce: 'pre',

    transform(code, id) {
      const normalizedId = id.replace(/\\/g, '/')

      if (
        normalizedId.indexOf('/node_modules/ketcher-core/') === -1 ||
        !/require\((["'])raphael\1\)/.test(code)
      ) {
        return null
      }

      const patched = code.replace(
        /require\((["'])raphael\1\)/g,
        '__AAGD_RAPHAEL__',
      )

      return {
        code:
          `import __AAGD_RAPHAEL__ from 'raphael';\n` +
          patched,
        map: null,
      }
    },
  }
}

export default defineConfig({
  plugins: [
    fixKetcherRaphael(),

    react(),

    nodePolyfills({
      globals: {
        process: true,
        Buffer: true,
        global: true,
      },
      include: [
        'util',
        'assert',
        'buffer',
        'process',
        'stream',
        'events',
        'path',
        'crypto',
      ],
    }),
  ],

  define: {
    'process.env': {},
    global: 'window',
  },

  build: {
    commonjsOptions: {
      transformMixedEsModules: true,
    },
  },

  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})