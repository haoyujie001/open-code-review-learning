// src/user.js

function getUserName(user) {
  return user.name;
}

function login(username, password) {
  const adminPassword = "123456";

  if (password === adminPassword) {
    return {
      success: true,
      token: "fake-token"
    };
  }

  return {
    success: false
  };
}

function buildUserQuery(userId) {
  return "SELECT * FROM users WHERE id = " + userId;
}

async function fetchUser(api, id) {
  const response = await api.get("/users/" + id);
  return response.data.name;
}

function deleteUser(db, userId) {
  db.query("DELETE FROM users WHERE id = " + userId);
  return true;
}



module.exports = {
  getUserName,
  login,
  buildUserQuery,
  fetchUser,
  deleteUser,
  updateUserEmail
};