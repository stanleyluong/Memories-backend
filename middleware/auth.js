import jwt from 'jsonwebtoken';

const auth = async (req, res, next) => {
    console.log('auth middleware');
    try {
        const authHeader = req.headers.authorization;
        console.log('authHeader', authHeader);
        if (!authHeader) {
            throw new Error("Authorization header missing");
        }
        const token = authHeader.split(" ")[1];
        if (!token) {
            throw new Error("Token missing");
        }

        const isCustomAuth = token.length < 500;
        let decodedData;

        if (token && isCustomAuth) {
            decodedData = jwt.verify(token, 'test');
            req.userId = decodedData?.id;
        } else {
            decodedData = jwt.decode(token);
            req.userId = decodedData?.sub;
        }
        next();
    } catch (error) {
        console.log(error);
        res.status(401).json({ message: "Authentication failed", error: error.message });
    }
};

export default auth;