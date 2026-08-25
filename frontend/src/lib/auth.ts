export const getStoredToken = (): string | null => {
  if (typeof window !== "undefined") {
    return localStorage.getItem("token");
  }
  return null;
};

export const setStoredToken = (token: string) => {
  if (typeof window !== "undefined") {
    localStorage.setItem("token", token);
  }
};

export const removeStoredToken = () => {
  if (typeof window !== "undefined") {
    localStorage.removeItem("token");
  }
};
