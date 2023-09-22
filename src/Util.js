import { APPNAME } from './Consts'

export const getLocalStorage = (key) => {
    const itemStr = localStorage.getItem(APPNAME + "." + key);
    if (!itemStr) {
        return null;
    }
    const item = JSON.parse(itemStr);
    const now = new Date().getTime();
    if (now > item.expiry) {
        localStorage.removeItem(APPNAME + "." + key);
        return null;
    }
    return item.value;
}

export const setLocalStorage = (k, v) => {
    const now = new Date();
    const endOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
    const expiry = endOfDay.getTime();
    const item = {
        value: v,
        expiry: expiry,
    };
    localStorage.setItem(APPNAME + "." + k, JSON.stringify(item));
}
export const emptyString = (str) => {
    return (!str || 0 === str.length);
}
