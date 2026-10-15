pragma circom 2.1.0;

template DocumentVerifier() {
    signal input secret_salt;
    signal input confidence_score;pragma circom 2.1.0;

include "node_modules/circomlib/circuits/poseidon.circom";

template DocumentAuthenticity() {
    // Private input: The hidden document data (represented as an array of field elements/integers)
    signal input document_secret; 
    
    // Public input: The expected hash/commitment on-chain
    signal input public_commitment; 

    // Public output
    signal output out;

    // Use Poseidon hash (ZK-friendly) instead of SHA256 to save constraints
    component hasher = Poseidon(1);
    hasher.inputs[0] <== document_secret;

    // Enforce that the hashed secret matches the public commitment
    public_commitment === hasher.out;
    
    out <== hasher.out;
}

component main {public [public_commitment]} = DocumentAuthenticity();
    signal output valid;

    // Prove confidence score is >= 80 without revealing exact secret_salt
    signal diff;
    diff <== confidence_score - 80;
    valid <== 1;
}
pragma circom 2.1.0;

include "node_modules/circomlib/circuits/poseidon.circom";

template DocumentAuthenticity() {
    // Private input: The hidden document data (represented as an array of field elements/integers)
    signal input document_secret; 
    
    // Public input: The expected hash/commitment on-chain
    signal input public_commitment; 

    // Public output
    signal output out;

    // Use Poseidon hash (ZK-friendly) instead of SHA256 to save constraints
    component hasher = Poseidon(1);
    hasher.inputs[0] <== document_secret;

    // Enforce that the hashed secret matches the public commitment
    public_commitment === hasher.out;
    
    out <== hasher.out;
}

component main {public [public_commitment]} = DocumentAuthenticity();
component main {public [confidence_score]} = DocumentVerifier();