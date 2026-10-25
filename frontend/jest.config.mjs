import nextJest from "next/jest.js";

const createJestConfig = nextJest({
  // caminho do app Next.js, para carregar next.config.ts e .env.* automaticamente
  dir: "./",
});

/** @type {import('jest').Config} */
const config = {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  testPathIgnorePatterns: ["<rootDir>/.next/", "<rootDir>/node_modules/", "<rootDir>/cypress/"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
  },
};

// next/jest cuida da transformação via SWC, mocks de CSS/imagens e variáveis de ambiente.
export default createJestConfig(config);
